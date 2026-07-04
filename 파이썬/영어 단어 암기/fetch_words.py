"""영한 사전(kengdic)에서 단어를 가져와 words.json을 생성합니다."""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
WORDS_FILE = APP_DIR / "words.json"
KENGdic_URL = "https://raw.githubusercontent.com/garfieldnate/kengdic/master/kengdic.tsv"
FREQUENCY_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/"
    "master/google-10000-english-no-swears.txt"
)

MAX_WORDS = 5000
MIN_LEN = 3
MAX_LEN = 18


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read().decode("utf-8")


def load_frequency_words() -> list[str]:
    try:
        text = download_text(FREQUENCY_URL)
    except OSError:
        return []
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def clean_korean(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"[~…\.]+$", "", text)
    return text[:80]


def pick_best_meaning(candidates: set[str]) -> str:
    cleaned = [clean_korean(c) for c in candidates if clean_korean(c)]
    if not cleaned:
        return ""

    scored: list[tuple[int, str]] = []
    for meaning in cleaned:
        score = 0
        if re.search(r"[가-힣]", meaning):
            score += 10
        if len(meaning) <= 12:
            score += 5
        if " " not in meaning:
            score += 3
        if re.search(r"[A-Za-z]", meaning):
            score -= 2
        if len(meaning) > 30:
            score -= 5
        scored.append((score, meaning))

    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return scored[0][1]


def eng_to_hangul_phonetic(word: str) -> str:
    """영어 단어를 학습용 한글 발음 표기로 대략 변환합니다."""
    w = word.lower()
    rules = [
        ("tion", "션"),
        ("sion", "션"),
        ("ture", "처"),
        ("ous", "어스"),
        ("ness", "니스"),
        ("ment", "먼트"),
        ("able", "어블"),
        ("ible", "어블"),
        ("ing", "잉"),
        ("igh", "아이"),
        ("ph", "프"),
        ("sh", "슈"),
        ("ch", "치"),
        ("th", "쓰"),
        ("ck", "크"),
        ("qu", "쿼"),
        ("ee", "이"),
        ("ea", "이"),
        ("oo", "우"),
        ("ai", "에이"),
        ("ay", "에이"),
        ("ey", "에이"),
        ("oa", "오"),
        ("ou", "아우"),
        ("ow", "오"),
        ("ue", "유"),
        ("wh", "워"),
        ("wr", "르"),
        ("kn", "느"),
        ("mb", "므"),
        ("sc", "스"),
        ("x", "엑스"),
        ("z", "즈"),
        ("y", "이"),
        ("c", "크"),
        ("q", "큐"),
        ("j", "제"),
        ("v", "브"),
        ("w", "워"),
        ("f", "프"),
        ("g", "그"),
        ("h", "흐"),
        ("k", "크"),
        ("l", "을"),
        ("m", "므"),
        ("n", "느"),
        ("p", "프"),
        ("r", "르"),
        ("s", "스"),
        ("t", "트"),
        ("b", "브"),
        ("d", "드"),
        ("a", "아"),
        ("e", "에"),
        ("i", "이"),
        ("o", "오"),
        ("u", "어"),
    ]

    result = []
    i = 0
    while i < len(w):
        matched = False
        for src, dst in rules:
            if w.startswith(src, i):
                result.append(dst)
                i += len(src)
                matched = True
                break
        if not matched:
            i += 1

    phonetic = "".join(result)
    phonetic = re.sub(r"(.)\1{2,}", r"\1\1", phonetic)
    return phonetic[:20] if phonetic else word


def parse_kengdic(text: str) -> dict[str, set[str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    entries: dict[str, set[str]] = defaultdict(set)

    for row in reader:
        gloss = (row.get("gloss") or "").strip()
        surface = (row.get("surface") or "").strip()
        if not gloss or not surface:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z\-']{1,17}", gloss):
            continue
        if not re.search(r"[가-힣]", surface):
            continue
        entries[gloss.lower()].add(surface)

    return entries


MEANING_PATTERN = re.compile(
    r"(다|하다|됨|하는|위한|것|점|력|성|화|적|자|용|류|법|식|지|물|구|트|들|,|을|를|에|의)"
)


def is_useful_entry(word: str, meaning: str, phonetic: str) -> bool:
    if not meaning or not re.search(r"[가-힣]", meaning):
        return False
    if meaning.replace(" ", "") == phonetic.replace(" ", ""):
        return False
    if re.search(r"[A-Za-z]", meaning):
        return False
    if not MEANING_PATTERN.search(meaning):
        return False
    return True


def build_word_list(
    dictionary: dict[str, set[str]],
    frequency_words: list[str],
    existing: list[dict],
) -> list[dict]:
    preserved: dict[str, dict] = {}
    for item in existing:
        word = item["word"].lower()
        phonetic = item.get("pronunciation", eng_to_hangul_phonetic(word))
        if is_useful_entry(word, item["meaning"], phonetic):
            preserved[word] = item

    results: list[dict] = [preserved[word] for word in sorted(preserved)]

    added = 0
    for rank, word in enumerate(frequency_words):
        if added >= max(0, MAX_WORDS - len(preserved)):
            break
        if rank >= 4500 and word not in preserved:
            continue
        if word in preserved or word not in dictionary:
            continue
        if not (MIN_LEN <= len(word) <= MAX_LEN):
            continue

        meaning = pick_best_meaning(dictionary[word])
        phonetic = eng_to_hangul_phonetic(word)
        if not is_useful_entry(word, meaning, phonetic):
            continue

        results.append(
            {
                "word": word,
                "meaning": meaning,
                "pronunciation": phonetic,
            }
        )
        added += 1

    results.sort(key=lambda item: item["word"])
    return results


def main() -> None:
    print("사전 데이터 다운로드 중...")
    kengdic_text = download_text(KENGdic_URL)
    dictionary = parse_kengdic(kengdic_text)
    print(f"사전에서 {len(dictionary):,}개 영어 단어를 찾았습니다.")

    existing = load_json(WORDS_FILE, [])
    frequency_words = load_frequency_words()
    print(f"빈도 기준 단어 {len(frequency_words):,}개를 참고합니다.")

    words = build_word_list(dictionary, frequency_words, existing)
    save_json(WORDS_FILE, words)
    print(f"words.json 저장 완료: {len(words):,}개 단어")


def load_json(path: Path, default):
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
