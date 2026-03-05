import os
from openai import OpenAI
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

# MJ-07 (V7): Cliente LLM con Fallback y degradación de confianza
class LLMClient:
    def __init__(self):
        self.mercury = OpenAI(
            api_key=os.environ.get("MERCURY_API_KEY"),
            base_url=os.environ.get("MERCURY_BASE_URL", "https://api.mercury2.ai/v1") # Ejemplo
        )
        self.groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.gemini_fallback = OpenAI(api_key=os.environ.get("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def completion(self, messages: list, model="mercury-2", temperature=0.7):
        try:
            # Intento principal con Mercury 2
            response = self.mercury.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return {
                "text": response.choices[0].message.content,
                "confidence_adjustment": 1.0,
                "source": "Mercury 2"
            }
        except Exception as e:
            logging.warning(f"Mercury 2 falló, intentando Groq: {str(e)}")
            try:
                # Fallback 1: Groq
                response = self.groq.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=messages
                )
                return {
                    "text": response.choices[0].message.content,
                    "confidence_adjustment": 0.85, # V7: -15% confidence
                    "source": "Groq [FALLBACK]"
                }
            except Exception as e2:
                logging.error(f"Groq falló, intentando Gemini: {str(e2)}")
                # Fallback final: Gemini
                response = self.gemini_fallback.chat.completions.create(
                    model="gemini-1.5-flash",
                    messages=messages
                )
                return {
                    "text": response.choices[0].message.content,
                    "confidence_adjustment": 0.70, # Mayor degradación
                    "source": "Gemini [FALLBACK]"
                }
