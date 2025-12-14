
import logging
from typing import Set, Optional, Tuple, Literal

logger = logging.getLogger(__name__)

class ShiritoriGame:
    def __init__(self):
        self.history: Set[str] = set()
        self.last_char: Optional[str] = None
        self.is_active: bool = False
    
    def start(self, start_char: str = "し") -> str:
        self.history.clear()
        self.last_char = start_char
        self.is_active = True
        return f"しりとりを開始しました！最初の文字は「{start_char}」です。"

    def end(self) -> str:
        self.is_active = False
        self.history.clear()
        self.last_char = None
        return "しりとりを終了しました。"

    def _normalize_reading(self, reading: str) -> str:
        # Simple normalization: keep only hiragana/katakana?
        # For now, just assume input is mostly correct hiragana.
        # Handle small chars: ぁ->あ, ゃ->や? 
        # Actually in Shiritori, "しゃ" -> "や" is common rule OR "しゃ" -> "ゃ" (invalid).
        # Standard rule: "しゃ" -> "や". "ー" (Long vowel) -> Ignore or previous vowel.
        # Let's keep it simple: Use the last character directly, but convert small to big.
        
        last = reading[-1]
        
        # Prolonged sound mark handling (Simple: prohibit words ending in ー for now, or just ignore it?)
        # Better: Convert to previous vowel. For simplicity, let's treat it as Invalid or strictly parse.
        # Common convention: "ー" is allowed, next char is the vowel. "コンピューター" -> "あ".
        # This is hard without conversion lib.
        # Alternative: Just take the last character.
        
        # Small Kana Map
        small_map = {
            'ぁ': 'あ', 'ぃ': 'い', 'ぅ': 'う', 'ぇ': 'え', 'o': 'お',
            'っ': 'つ', 'ゃ': 'や', 'ゅ': 'ゆ', 'ょ': 'よ',
            'ゎ': 'わ',
            'ァ': 'ア', 'ィ': 'イ', 'ゥ': 'ウ', 'ェ': 'エ', 'ォ': 'オ',
            'ッ': 'ツ', 'ャ': 'ヤ', 'ュ': 'ユ', 'ョ': 'ヨ',
            'ヮ': 'ワ',
            'ー': '-' # Mark for special handling
        }
        
        if last in small_map:
            return small_map[last]
        
        return last

    def check_move(self, word: str, reading: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a move.
        Returns: (IsValid, Message, NextChar)
        """
        if not self.is_active:
            return False, "ゲームが開始されていません。「しりとり開始」と言ってください。", None

        # 1. Check 'N'
        if reading.endswith("ん") or reading.endswith("ン"):
            self.is_active = False
            return False, f"「{word} ({reading})」は「ん」で終わっています！あなたの負けです！", None

        # 2. Check Connection
        if self.last_char:
            # Normalize start of this word?
            # Usually strict equality.
            if not reading.startswith(self.last_char):
                 return False, f"「{word} ({reading})」は「{self.last_char}」から始まっていません！", self.last_char

        # 3. Check Duplicates
        if word in self.history:
             return False, f"「{word}」は既に出ています！", self.last_char

        # Valid!
        self.history.add(word)
        
        # Determine next char
        next_char = self._normalize_reading(reading)
        
        # Pass logic for "ー" (Prolonged).
        # If result is "-", it means word ended in ー.
        if next_char == "-":
             # Fallback: Look at second to last char
             if len(reading) > 1:
                 second_last = reading[-2]
                 # Convert vowel... complex.
                 # Let's just say "Ends in ー is forbidden" for simplicity or just ignore it.
                 # "Start with ー" is impossible.
                 # Let's use the vowel of the character before ー.
                 # Too complex for regex‐less pure python quickly?
                 # Vowel map:
                 vowels = {
                     'あ': 'あ', 'か': 'あ', 'さ': 'あ', 'た': 'あ', 'な': 'あ', 'は': 'あ', 'ま': 'あ', 'や': 'あ', 'ら': 'あ', 'わ': 'あ',
                     'い': 'い', 'き': 'い', 'し': 'い', 'ち': 'い', 'に': 'い', 'ひ': 'い', 'み': 'い', 'り': 'い',
                     'う': 'う', 'く': 'う', 'す': 'う', 'つ': 'う', 'ぬ': 'う', 'ふ': 'う', 'む': 'う', 'ゆ': 'う', 'る': 'う',
                     'え': 'え', 'け': 'え', 'せ': 'え', 'て': 'え', 'ね': 'え', 'へ': 'え', 'め': 'え', 'れ': 'え',
                     'お': 'お', 'こ': 'お', 'そ': 'お', 'と': 'お', 'の': 'お', 'ほ': 'お', 'も': 'お', 'よ': 'お', 'ろ': 'お', 'を': 'お'
                 }
                 # Simplified map.
                 # Actually, most people play rule: "ー" -> Preceding Vowel.
                 # This is too much logic for now.
                 # Let's just return the raw character before 'ー' if possible, or 'あ' as fail safe?
                 # Safer: Disallow words ending in ー.
                 return False, f"「{word}」は「ー」で終わっています。長音で終わる単語は禁止です（判定が難しいため）。", self.last_char
        
        self.last_char = next_char
        return True, "OK", next_char

