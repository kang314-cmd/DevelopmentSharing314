"""영어 단어 암기 앱 (tkinter)"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
WORDS_FILE = APP_DIR / "words.json"
DATA_DIR = APP_DIR / "data"
LEARNED_FILE = DATA_DIR / "learned_words.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

SESSION_SIZE = 40
DEFAULT_PASS_RATE = 80

COLORS = {
    "bg": "#f0f4f8",
    "card_front": "#ffffff",
    "card_back": "#e8f5e9",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "text": "#1e293b",
    "muted": "#64748b",
    "success": "#16a34a",
    "danger": "#dc2626",
    "border": "#cbd5e1",
}


def load_json(path: Path, default):
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class SpeechEngine:
    """영어 단어 발음 재생 (pyttsx3 우선, Windows SAPI 대체)."""

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 150)
            voices = self._engine.getProperty("voices")
            for voice in voices:
                if "english" in voice.name.lower() or "en" in voice.id.lower():
                    self._engine.setProperty("voice", voice.id)
                    break
        except Exception:
            self._engine = None

    def speak(self, text: str) -> None:
        threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()

    def _speak_sync(self, text: str) -> None:
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                    return
                except Exception:
                    pass
            self._speak_windows(text)

    @staticmethod
    def _speak_windows(text: str) -> None:
        if sys.platform != "win32":
            return
        safe = text.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{safe}')"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=False,
                capture_output=True,
            )
        except OSError:
            pass


class WordStore:
    def __init__(self) -> None:
        self.all_words: list[dict] = load_json(WORDS_FILE, [])
        self.learned_words: list[dict] = load_json(LEARNED_FILE, [])
        self.settings: dict = load_json(
            SETTINGS_FILE,
            {"pass_rate": DEFAULT_PASS_RATE, "speech_rate": 150},
        )

    @property
    def learned_set(self) -> set[str]:
        return {item["word"] for item in self.learned_words}

    def save_learned(self) -> None:
        save_json(LEARNED_FILE, self.learned_words)

    def save_settings(self) -> None:
        save_json(SETTINGS_FILE, self.settings)

    def select_session_words(self, count: int = SESSION_SIZE) -> list[dict]:
        pool = [w for w in self.all_words if w["word"] not in self.learned_set]
        if len(pool) < count:
            return random.sample(pool, len(pool)) if pool else []
        return random.sample(pool, count)

    def mark_learned(self, words: list[dict]) -> None:
        existing = self.learned_set
        for word in words:
            if word["word"] not in existing:
                self.learned_words.append(
                    {
                        "word": word["word"],
                        "meaning": word["meaning"],
                        "pronunciation": word.get("pronunciation", ""),
                    }
                )
        self.save_learned()

    def reset_learned(self) -> None:
        self.learned_words.clear()
        self.save_learned()


class VocabularyApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("영어 단어 암기")
        self.geometry("520x680")
        self.minsize(480, 620)
        self.configure(bg=COLORS["bg"])

        self.store = WordStore()
        self.speech = SpeechEngine()
        self.session_words: list[dict] = []
        self.wrong_words: list[dict] = []
        self.current_index = 0
        self.card_flipped = False

        self.title_font = font.Font(family="Malgun Gothic", size=22, weight="bold")
        self.word_font = font.Font(family="Segoe UI", size=32, weight="bold")
        self.meaning_font = font.Font(family="Malgun Gothic", size=20)
        self.body_font = font.Font(family="Malgun Gothic", size=12)
        self.btn_font = font.Font(family="Malgun Gothic", size=13, weight="bold")

        self.container = tk.Frame(self, bg=COLORS["bg"])
        self.container.pack(fill=tk.BOTH, expand=True)

        self.show_main_menu()

    def clear_container(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_main_menu(self) -> None:
        self.clear_container()
        self.session_words = []
        self.wrong_words = []

        wrapper = tk.Frame(self.container, bg=COLORS["bg"])
        wrapper.pack(expand=True)

        tk.Label(
            wrapper,
            text="영어 단어 암기",
            font=self.title_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(40, 8))

        tk.Label(
            wrapper,
            text=f"전체 {len(self.store.all_words)}개 · 학습 완료 {len(self.store.learned_words)}개",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(0, 36))

        buttons = [
            ("단어 암기 시작", self.start_study),
            ("학습한 단어 보기", self.show_learned_words),
            ("설정", self.show_settings),
            ("종료", self.quit),
        ]
        for text, command in buttons:
            self._make_button(wrapper, text, command).pack(pady=8, ipadx=20, ipady=6)

    def start_study(self) -> None:
        self.session_words = self.store.select_session_words()
        if not self.session_words:
            messagebox.showinfo(
                "알림",
                "학습할 단어가 없습니다.\n모든 단어를 학습했거나 단어 목록이 비어 있습니다.",
            )
            return
        if len(self.session_words) < SESSION_SIZE:
            messagebox.showinfo(
                "알림",
                f"학습 완료된 단어를 제외하고 {len(self.session_words)}개의 단어로 학습을 시작합니다.",
            )
        self.current_index = 0
        self.card_flipped = False
        self.show_study_screen()

    def show_study_screen(self) -> None:
        self.clear_container()
        self.card_flipped = False

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill=tk.X, padx=20, pady=(16, 8))

        self._make_button(header, "← 메인", self.show_main_menu, small=True).pack(side=tk.LEFT)

        self.progress_label = tk.Label(
            header,
            text="",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        )
        self.progress_label.pack(side=tk.RIGHT)

        self.card_frame = tk.Frame(
            self.container,
            bg=COLORS["card_front"],
            highlightbackground=COLORS["border"],
            highlightthickness=2,
        )
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)
        self.card_frame.bind("<Button-1>", lambda _e: self.flip_card())

        self.card_content = tk.Frame(self.card_frame, bg=COLORS["card_front"])
        self.card_content.pack(fill=tk.BOTH, expand=True)
        self.card_content.bind("<Button-1>", lambda _e: self.flip_card())

        nav = tk.Frame(self.container, bg=COLORS["bg"])
        nav.pack(fill=tk.X, padx=24, pady=8)

        self._make_button(nav, "◀ 이전", self.prev_card, small=True).pack(side=tk.LEFT)
        self._make_button(nav, "카드 뒤집기", self.flip_card, small=True).pack(side=tk.LEFT, padx=8)
        self._make_button(nav, "다음 ▶", self.next_card, small=True).pack(side=tk.LEFT)

        bottom = tk.Frame(self.container, bg=COLORS["bg"])
        bottom.pack(fill=tk.X, padx=24, pady=(8, 20))

        self._make_button(bottom, "테스트 시작", self.start_test, accent=True).pack(fill=tk.X, ipady=8)

        tk.Label(
            bottom,
            text="카드를 클릭해도 앞뒤를 뒤집을 수 있습니다.",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(10, 0))

        self.render_card()

    def render_card(self) -> None:
        for widget in self.card_content.winfo_children():
            widget.destroy()

        word_data = self.session_words[self.current_index]
        total = len(self.session_words)
        self.progress_label.config(text=f"{self.current_index + 1} / {total}")

        bg = COLORS["card_back"] if self.card_flipped else COLORS["card_front"]
        self.card_frame.configure(bg=bg)
        self.card_content.configure(bg=bg)

        top_bar = tk.Frame(self.card_content, bg=bg)
        top_bar.pack(fill=tk.X, padx=12, pady=12)

        if not self.card_flipped:
            speaker_btn = tk.Button(
                top_bar,
                text="🔊",
                font=self.body_font,
                bg=bg,
                fg=COLORS["accent"],
                activebackground=bg,
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda w=word_data["word"]: self.speech.speak(w),
            )
            speaker_btn.pack(side=tk.RIGHT)

        center = tk.Frame(self.card_content, bg=bg)
        center.pack(expand=True)

        if self.card_flipped:
            tk.Label(
                center,
                text=word_data["meaning"],
                font=self.meaning_font,
                bg=bg,
                fg=COLORS["text"],
                wraplength=400,
                justify=tk.CENTER,
            ).pack(expand=True)
            tk.Label(
                center,
                text="뜻",
                font=self.body_font,
                bg=bg,
                fg=COLORS["muted"],
            ).pack(pady=(0, 20))
        else:
            tk.Label(
                center,
                text=word_data["word"],
                font=self.word_font,
                bg=bg,
                fg=COLORS["accent"],
            ).pack(expand=True)
            pron = word_data.get("pronunciation", "")
            if pron:
                tk.Label(
                    center,
                    text=f"[{pron}]",
                    font=self.body_font,
                    bg=bg,
                    fg=COLORS["muted"],
                ).pack(pady=(0, 20))

    def flip_card(self) -> None:
        self.card_flipped = not self.card_flipped
        self.render_card()

    def prev_card(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.card_flipped = False
            self.render_card()

    def next_card(self) -> None:
        if self.current_index < len(self.session_words) - 1:
            self.current_index += 1
            self.card_flipped = False
            self.render_card()

    def start_test(self) -> None:
        if not self.session_words:
            return
        self.wrong_words = []
        self.test_index = 0
        self.test_correct = 0
        self.test_questions = self._build_test_questions()
        self.show_test_screen()

    def _build_test_questions(self) -> list[dict]:
        questions = []
        all_words = self.store.all_words
        for word_data in self.session_words:
            q_type = random.choice(["en_to_ko", "ko_to_en", "listen"])
            distractors = [w for w in all_words if w["word"] != word_data["word"]]
            wrong_pool = random.sample(distractors, min(3, len(distractors)))

            if q_type == "en_to_ko":
                choices = [word_data["meaning"]] + [w["meaning"] for w in wrong_pool]
                random.shuffle(choices)
                questions.append(
                    {
                        "type": q_type,
                        "word": word_data,
                        "prompt": word_data["word"],
                        "sub_prompt": "아래에서 올바른 뜻을 고르세요.",
                        "answer": word_data["meaning"],
                        "choices": choices,
                    }
                )
            elif q_type == "ko_to_en":
                choices = [word_data["word"]] + [w["word"] for w in wrong_pool]
                random.shuffle(choices)
                questions.append(
                    {
                        "type": q_type,
                        "word": word_data,
                        "prompt": word_data["meaning"],
                        "sub_prompt": "아래에서 올바른 영어 단어를 고르세요.",
                        "answer": word_data["word"],
                        "choices": choices,
                    }
                )
            else:
                choices_meaning = [word_data["meaning"]] + [w["meaning"] for w in wrong_pool]
                choices_word = [word_data["word"]] + [w["word"] for w in wrong_pool]
                paired = list(zip(choices_word, choices_meaning))
                random.shuffle(paired)
                questions.append(
                    {
                        "type": q_type,
                        "word": word_data,
                        "prompt": "발음을 듣고 맞는 단어와 뜻을 고르세요.",
                        "sub_prompt": "",
                        "answer": (word_data["word"], word_data["meaning"]),
                        "choices": paired,
                    }
                )
        random.shuffle(questions)
        return questions

    def show_test_screen(self) -> None:
        self.clear_container()
        question = self.test_questions[self.test_index]
        total = len(self.test_questions)

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill=tk.X, padx=20, pady=(16, 8))
        self._make_button(header, "← 학습으로", self.show_study_screen, small=True).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"테스트 {self.test_index + 1} / {total}",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(side=tk.RIGHT)

        type_labels = {
            "en_to_ko": "영어 → 뜻 맞추기",
            "ko_to_en": "뜻 → 영어 맞추기",
            "listen": "발음 듣고 맞추기",
        }
        tk.Label(
            self.container,
            text=type_labels[question["type"]],
            font=self.title_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(12, 4))

        prompt_frame = tk.Frame(self.container, bg=COLORS["card_front"], highlightbackground=COLORS["border"], highlightthickness=2)
        prompt_frame.pack(fill=tk.X, padx=24, pady=12, ipady=20)

        if question["type"] == "listen":
            listen_row = tk.Frame(prompt_frame, bg=COLORS["card_front"])
            listen_row.pack()
            tk.Label(
                listen_row,
                text=question["prompt"],
                font=self.meaning_font,
                bg=COLORS["card_front"],
                fg=COLORS["text"],
            ).pack(side=tk.LEFT, padx=(0, 12))
            tk.Button(
                listen_row,
                text="🔊 다시 듣기",
                font=self.body_font,
                bg=COLORS["accent"],
                fg="white",
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda w=question["word"]["word"]: self.speech.speak(w),
            ).pack(side=tk.LEFT)
            self.after(300, lambda w=question["word"]["word"]: self.speech.speak(w))
        else:
            tk.Label(
                prompt_frame,
                text=question["prompt"],
                font=self.word_font if question["type"] == "en_to_ko" else self.meaning_font,
                bg=COLORS["card_front"],
                fg=COLORS["accent"] if question["type"] == "en_to_ko" else COLORS["text"],
                wraplength=420,
                justify=tk.CENTER,
            ).pack()

        if question["sub_prompt"]:
            tk.Label(
                self.container,
                text=question["sub_prompt"],
                font=self.body_font,
                bg=COLORS["bg"],
                fg=COLORS["muted"],
            ).pack(pady=(0, 8))

        choices_frame = tk.Frame(self.container, bg=COLORS["bg"])
        choices_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=8)

        for choice in question["choices"]:
            if question["type"] == "listen":
                label = f"{choice[0]}  —  {choice[1]}"
            else:
                label = choice
            btn = tk.Button(
                choices_frame,
                text=label,
                font=self.body_font,
                bg="white",
                fg=COLORS["text"],
                activebackground=COLORS["card_back"],
                relief=tk.GROOVE,
                cursor="hand2",
                anchor=tk.W,
                padx=16,
                pady=10,
                command=lambda c=choice, q=question: self.check_answer(q, c),
            )
            btn.pack(fill=tk.X, pady=4)

    def check_answer(self, question: dict, choice) -> None:
        correct = choice == question["answer"]
        word_data = question["word"]

        if correct:
            self.test_correct += 1
            messagebox.showinfo("정답", "맞았습니다!")
        else:
            if word_data not in self.wrong_words:
                self.wrong_words.append(word_data)
            if question["type"] == "listen":
                ans_text = f"{question['answer'][0]} — {question['answer'][1]}"
            else:
                ans_text = question["answer"]
            messagebox.showwarning("오답", f"틀렸습니다.\n정답: {ans_text}")

        self.test_index += 1
        if self.test_index >= len(self.test_questions):
            self.show_test_result()
        else:
            self.show_test_screen()

    def show_test_result(self) -> None:
        total = len(self.test_questions)
        rate = round(self.test_correct / total * 100) if total else 0
        pass_rate = self.store.settings.get("pass_rate", DEFAULT_PASS_RATE)
        passed = rate >= pass_rate

        self.clear_container()

        tk.Label(
            self.container,
            text="테스트 결과",
            font=self.title_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(40, 12))

        tk.Label(
            self.container,
            text=f"{self.test_correct} / {total}  ({rate}%)",
            font=self.word_font,
            bg=COLORS["bg"],
            fg=COLORS["success"] if passed else COLORS["danger"],
        ).pack(pady=8)

        if passed:
            wrong_set = {w["word"] for w in self.wrong_words}
            learned = [w for w in self.session_words if w["word"] not in wrong_set]
            self.store.mark_learned(learned)
            tk.Label(
                self.container,
                text=f"합격! {len(learned)}개 단어가 학습 완료 목록에 저장되었습니다.",
                font=self.body_font,
                bg=COLORS["bg"],
                fg=COLORS["text"],
                wraplength=420,
                justify=tk.CENTER,
            ).pack(pady=12)
        else:
            tk.Label(
                self.container,
                text=f"합격 기준 {pass_rate}%에 미달했습니다.\n틀린 단어는 다음 학습에 다시 나올 수 있습니다.",
                font=self.body_font,
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                wraplength=420,
                justify=tk.CENTER,
            ).pack(pady=12)

        if self.wrong_words:
            wrong_text = ", ".join(w["word"] for w in self.wrong_words)
            tk.Label(
                self.container,
                text=f"틀린 단어: {wrong_text}",
                font=self.body_font,
                bg=COLORS["bg"],
                fg=COLORS["danger"],
                wraplength=420,
                justify=tk.CENTER,
            ).pack(pady=8)

        btn_frame = tk.Frame(self.container, bg=COLORS["bg"])
        btn_frame.pack(pady=24)
        self._make_button(btn_frame, "메인으로", self.show_main_menu).pack(pady=6, ipadx=16, ipady=4)
        if not passed:
            self._make_button(btn_frame, "다시 학습", self.show_study_screen).pack(pady=6, ipadx=16, ipady=4)

    def show_learned_words(self) -> None:
        self.clear_container()

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill=tk.X, padx=20, pady=(16, 8))
        self._make_button(header, "← 메인", self.show_main_menu, small=True).pack(side=tk.LEFT)

        tk.Label(
            self.container,
            text=f"학습한 단어 ({len(self.store.learned_words)}개)",
            font=self.title_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(8, 12))

        if not self.store.learned_words:
            tk.Label(
                self.container,
                text="아직 학습 완료한 단어가 없습니다.",
                font=self.body_font,
                bg=COLORS["bg"],
                fg=COLORS["muted"],
            ).pack(pady=40)
            return

        list_frame = tk.Frame(self.container, bg=COLORS["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORS["bg"])

        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for idx, item in enumerate(sorted(self.store.learned_words, key=lambda x: x["word"])):
            row = tk.Frame(inner, bg="white", highlightbackground=COLORS["border"], highlightthickness=1)
            row.pack(fill=tk.X, pady=3, padx=2)

            tk.Label(
                row,
                text=item["word"],
                font=font.Font(family="Segoe UI", size=14, weight="bold"),
                bg="white",
                fg=COLORS["accent"],
                width=16,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=12, pady=8)

            tk.Label(
                row,
                text=item["meaning"],
                font=self.body_font,
                bg="white",
                fg=COLORS["text"],
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=4, pady=8)

            tk.Button(
                row,
                text="🔊",
                font=self.body_font,
                bg="white",
                fg=COLORS["accent"],
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda w=item["word"]: self.speech.speak(w),
            ).pack(side=tk.RIGHT, padx=8)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    def show_settings(self) -> None:
        self.clear_container()

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill=tk.X, padx=20, pady=(16, 8))
        self._make_button(header, "← 메인", self.show_main_menu, small=True).pack(side=tk.LEFT)

        tk.Label(
            self.container,
            text="설정",
            font=self.title_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(8, 24))

        form = tk.Frame(self.container, bg=COLORS["bg"])
        form.pack(padx=40)

        tk.Label(
            form,
            text="테스트 합격 기준 (%)",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).grid(row=0, column=0, sticky=tk.W, pady=8)

        pass_var = tk.StringVar(value=str(self.store.settings.get("pass_rate", DEFAULT_PASS_RATE)))
        pass_entry = tk.Entry(form, textvariable=pass_var, font=self.body_font, width=8)
        pass_entry.grid(row=0, column=1, sticky=tk.W, padx=12, pady=8)

        tk.Label(
            form,
            text="한 세션 단어 수",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).grid(row=1, column=0, sticky=tk.W, pady=8)

        tk.Label(
            form,
            text=f"{SESSION_SIZE}개 (고정)",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).grid(row=1, column=1, sticky=tk.W, padx=12, pady=8)

        def save_settings() -> None:
            try:
                rate = int(pass_var.get())
                if not 1 <= rate <= 100:
                    raise ValueError
            except ValueError:
                messagebox.showerror("오류", "합격 기준은 1~100 사이의 정수로 입력하세요.")
                return
            self.store.settings["pass_rate"] = rate
            self.store.save_settings()
            messagebox.showinfo("저장", "설정이 저장되었습니다.")

        btn_row = tk.Frame(self.container, bg=COLORS["bg"])
        btn_row.pack(pady=24)
        self._make_button(btn_row, "저장", save_settings, accent=True).pack(pady=6, ipadx=20, ipady=4)

        tk.Label(
            self.container,
            text="학습 완료 기록 초기화",
            font=self.body_font,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(pady=(32, 8))

        def reset_learned() -> None:
            if messagebox.askyesno("확인", "학습한 단어 기록을 모두 삭제할까요?"):
                self.store.reset_learned()
                messagebox.showinfo("완료", "학습 기록이 초기화되었습니다.")

        self._make_button(self.container, "학습 기록 초기화", reset_learned, danger=True).pack(ipadx=12, ipady=4)

    def _make_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        small: bool = False,
        accent: bool = False,
        danger: bool = False,
    ) -> tk.Button:
        if danger:
            bg, fg, active_bg = COLORS["danger"], "white", "#b91c1c"
        elif accent:
            bg, fg, active_bg = COLORS["accent"], "white", COLORS["accent_hover"]
        else:
            bg, fg, active_bg = "white", COLORS["text"], COLORS["card_back"]

        return tk.Button(
            parent,
            text=text,
            font=self.body_font if small else self.btn_font,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief=tk.FLAT if accent or danger else tk.GROOVE,
            cursor="hand2",
            command=command,
            padx=12 if small else 20,
            pady=4 if small else 6,
        )


def main() -> None:
    app = VocabularyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
