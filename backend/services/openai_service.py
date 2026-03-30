import os
from openai import AsyncOpenAI
from config import settings
from typing import AsyncGenerator, List, Dict

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_gpt_response_stream(
    prompt: str, 
    history: List[Dict[str, str]], 
    context_data: str = ""
) -> AsyncGenerator[str, None]:
    """
    GPT-4o-mini kullanarak doğal ve akıcı bir yanıt üretir.
    Gemini'den gelen teknik verileri (context_data) kullanıcıya samimi bir dille sunar.
    """
    
    system_instruction = (
        "Sen Ela'sın. Profesyonel, cana yakın ve çözüm odaklı bir otobüs bileti asistanısın. "
        "Görevin, veritabanından gelen ham verileri veya Gemini'nin teknik kararlarını "
        "son derece doğal ve akıcı bir insan diliyle kullanıcıya sunmaktır. "
        "Sıcak bir karşılama, yardımcı bir tavır ve net ifadeler kullan.\n"
        "Önemli: Yanıtların her zaman <|ACT:...|> token'ı ile başlamalıdır."
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    
    # Geçmişi ekle
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Mevcut veriyi ve kullanıcı sorusunu ekle
    user_content = prompt
    if context_data:
        user_content = f"Sistemden Gelen Veri: {context_data}\n\nKullanıcı Sorusu: {prompt}\n\nBu veriyi kullanarak kullanıcıya doğal bir cevap ver."
    
    messages.append({"role": "user", "content": user_content})

    try:
        stream = await client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=messages,
            stream=True,
            temperature=0.7
        )
        
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        yield f"Hata: OpenAI servisi şu an yanıt veremiyor ({str(e)})"
