import asyncio
import os
import edge_tts

VOICE = "az-AZ-BanuNeural"  # Microsoft Neural Azerbaijani Female Voice

PHRASES = {
    "listen.mp3": "Eşidirəm, buyurun",
    "call_sister_confirm.mp3": "Bacınız Almaz xalaya zəng edilsin? Bəli deyin.",
    "call_daughter_confirm.mp3": "Qızınız Sevincə zəng edilsin? Bəli deyin.",
    "call_mother_confirm.mp3": "Mamanıza zəng edilsin? Bəli deyin.",
    "call_doctor_confirm.mp3": "Doktor Nigar Həkimə zəng edilsin? Bəli deyin.",
    "call_sister_active.mp3": "Almaz xala ilə əlaqə qurulur.",
    "call_daughter_active.mp3": "Sevinc ilə əlaqə qurulur.",
    "call_mother_active.mp3": "Mama ilə əlaqə qurulur.",
    "call_end.mp3": "Zəng başa çatdı.",
    "chef_tantuni_confirm.mp3": "Chef Tantunidən bir pors Tantuni sifarişiniz təsdiqlənsin? Cəmi səkkiz manat əlli qəpik. Bəli deyin.",
    "chef_tantuni_active.mp3": "Chef Tantunidən sifarişiniz qəbul olundu. Kuryer yoldadır.",
    "pharmacy_confirm.mp3": "Aptekdən kardiomaqnil dərmanı sifarişiniz təsdiqlənsin? Cəmi altı manat iyirmi qəpik. Bəli deyin.",
    "pharmacy_active.mp3": "Aptekdən sifarişiniz qəbul olundu. Kuryer yoldadır.",
    "taxi_confirm.mp3": "Nizami küçəsindən şəhər mərkəzinə taksi çağırılsın? Qiymət beş manat. Bəli deyin.",
    "taxi_active.mp3": "Taksi təsdiqləndi. Toyota Camry üç dəqiqəyə çatır.",
    "reminders.mp3": "Xatırlatmalarınız ekrandadır.",
    "order_done.mp3": "Sifarişiniz tamamlandı. Nuş olsun!",
    "action_cancel.mp3": "Əməliyyat ləğv edildi."
}

async def generate():
    # Single frontend source: public/ (served by Vercel directly and by FastAPI locally)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(repo_root, "public", "static", "audio")
    os.makedirs(out_dir, exist_ok=True)

    for filename, text in PHRASES.items():
        path = os.path.join(out_dir, filename)
        print(f"Generating {filename}: '{text}'...")
        await edge_tts.Communicate(text, VOICE).save(path)
        print(f"Saved: {path} ({os.path.getsize(path)} bytes)")

    print("All Azerbaijani voice audio generated successfully!")


if __name__ == "__main__":
    asyncio.run(generate())
