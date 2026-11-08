"""
Verification of Decision Tree & Safety Pipeline on completely unseen Azerbaijani sentences.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.models.predict import IntentPredictor

def verify():
    predictor = IntentPredictor()
    test_utterances = [
        "Qadan alım, mənə Wolt-dan bir pors isti düşbərə zakaz elə.",
        "Balam, qızıma zvanok at görüm harda qaldı axı.",
        "Axşam saat doqquzda təzyiq dərmanımı içməyi unutmayım, xəbər ver.",
        "Boğuluram, nəfəs ala bilmirəm, təcili 103 çağır!",
        "Sabah Şəkidə hava necə olacaq, yağış yağacaq?",
        "Səninlə danışanda bütün dərdim yadımdan çıxır, çox sağ ol.",
        "Bəlkə də elədir, bilmirəm dəqiq nə etmək olar."
    ]

    print("=== TESTING UNSEEN AZERBAIJANI SENTENCES ===\n")
    for utt in test_utterances:
        res = predictor.predict(utt)
        print(f"Utterance: \"{utt}\"")
        print(f"  Predicted Intent:       {res['intent']}")
        print(f"  Confidence:             {res['confidence']:.4f}")
        print(f"  Recommended Action:     {res['recommended_action']}")
        print(f"  Requires Clarification: {res['requires_clarification']}")
        if res.get("entities", {}).get("items"):
            print(f"  Extracted Items:        {res['entities']['items']}")
        if res.get("safety_escalation"):
            print(f"  Safety Escalated:       {res['safety_escalation']}")
        print("-" * 65)

if __name__ == "__main__":
    verify()

