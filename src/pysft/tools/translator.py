''' 
This module contains hebrew to english translation solution tool for PySFT.
'''

from typing import Optional, Literal
import asyncio

import requests
from googletrans import Translator

TRANSLATOR_TIMEOUT_SECONDS = 6
TRANSLATOR_MAX_CHUNK_SIZE = 200  # max characters per translation chunk

class He2En_Translator:
    '''
    A simple translator class for translating Hebrew financial terms to English.
    Translation providers: 'mymemory', 'google translate'
    '''
    # def __init__(self, email: Optional[str] = None, timeout: int = 6):
    #     self.email = email            # optional email to raise MyMemory limits
    #     self.timeout = timeout
    #     self._google = None           # lazy googletrans translator

    _google = Translator()

    @staticmethod
    def translate(text: str, source: Literal["google", "mymemory", "both"] = "google") -> str:
        '''
        Translate the given Hebrew text to English using available providers.
        Args:
            text (str): The Hebrew text to translate.
        Returns:
            str: The translated English text, or an empty string if translation fails.
        '''
        chunks = []
        seperators = []
        if len(text) > TRANSLATOR_MAX_CHUNK_SIZE:
            splitted_text = text.split('.')
            for part in splitted_text:
                if part.__len__() > TRANSLATOR_MAX_CHUNK_SIZE:
                    sub_parts = part.split(',')
                    for sub in sub_parts:
                        chunks.append(sub)
                        seperators.append(', ')

                    seperators[-1] = '. '
                else:
                    chunks.append(part)
                    seperators.append('. ')
        else:
            chunks = [text]
            seperators = ['']

        if not text:
            return ""
        try:
            translated_text = ""
            for chunk, separator in zip(chunks, seperators):
                if source in ["mymemory", "both"]:
                    # Translate using MyMemory API
                    t = He2En_Translator._translate_mymemory(chunk)    
                    if t:
                        translated_text += t + separator
                    else:
                        # fallback to google if mymemory fails
                        t = He2En_Translator._translate_google(chunk)
                        if t:
                            translated_text += t + separator

                if source == "google":
                    # Translate using googletrans
                    t = He2En_Translator._translate_google(chunk)
                    if t:
                       translated_text += t + separator

            return translated_text
        except Exception:
            return ""

    @staticmethod
    def _translate_mymemory(text: str) -> str:
        '''
        Translate using MyMemory API.
        Args:
            text (str): The Hebrew text to translate.
        Returns:
            str: The translated English text, or an empty string if translation fails.
        '''
        params = {'q': text, 'langpair': 'he|en'}
        # if self.email:
        #     params['de'] = self.email
        r = requests.get('https://api.mymemory.translated.net/get', params=params, timeout=TRANSLATOR_TIMEOUT_SECONDS)
        if r.status_code != 200:
            return ""
        data = r.json()
        return (data.get('responseData', {}).get('translatedText') or "").strip()

    @staticmethod
    def _translate_google(text: str) -> str:
        '''
        Translate using googletrans library.
        Args:
            text (str): The Hebrew text to translate.
        Returns:
            str: The translated English text.
        '''
        tr = He2En_Translator._google.translate(text, src='he', dest='en')

        if asyncio.iscoroutine(tr):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(tr).text
            # Already in event loop; cannot await in a sync method
            raise RuntimeError("Async translate detected. Use He2En_Translator.atranslate() in an async context.")
        return getattr(tr, "text", str(tr))