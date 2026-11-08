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
    "action_cancel.mp3": "Əməliyyat ləğv edildi.",
    "call_nene_confirm.mp3": "Nənənizə zəng edilsin? Bəli deyin.",
    "call_nene_active.mp3": "Nənəniz ilə əlaqə qurulur.",
    "not_understood.mp3": "Bağışlayın, tam başa düşmədim. Zəhmət olmasa təkrar edin."
}

async def generate():
    # public/ is the single source for the web UI; the backend serves files from there too.
    out_dir_pub = os.path.join("public", "static", "audio")
    os.makedirs(out_dir_pub, exist_ok=True)

    for filename, text in PHRASES.items():
        pub_path = os.path.join(out_dir_pub, filename)
        print(f"Generating {filename}: '{text}'...")
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(pub_path)
        print(f"Saved: {pub_path} ({os.path.getsize(pub_path)} bytes)")

    print("All Azerbaijani voice audio generated successfully!")

if __name__ == "__main__":
    asyncio.run(generate())

