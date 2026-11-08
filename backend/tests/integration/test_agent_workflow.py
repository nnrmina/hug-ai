from app.agents.graph import run_agent_workflow


def test_contact_agent_requires_confirmation_and_local_lookup():
    state = run_agent_workflow("user-1", "Yaxın, qızıma zəng et")
    assert state["intent"] == "MAKE_CALL"
    assert state["requires_confirmation"] is True
    assert state["status"] == "needs_confirmation"
    assert state["action_data"]["contact_alias"] == "qızım"
    assert state["action_data"]["local_only"] is True


def test_reminder_agent_workflow():
    state = run_agent_workflow("user-1", "Sabah saat 9-da məni oyat")
    assert state["intent"] == "CREATE_REMINDER"
    assert state["requires_confirmation"] is True
    assert state["status"] == "needs_confirmation"
    assert "scheduled_at" in state["action_data"]


def test_security_agent_scam_detection():
    state = run_agent_workflow(
        "user-1",
        "Bank hesabınız bloklanıb. Təcili linkə daxil olun və kart məlumatlarını yazın: http://bit.ly/fake",
    )
    assert state["intent"] == "ANALYZE_MESSAGE"
    assert state["status"] == "completed"
    assert state["action_data"]["risk_level"] == "high"
    assert "credential_request" in state["action_data"]["indicators"]


def test_blocked_high_risk_actions():
    bank_state = run_agent_workflow("user-1", "Kartımdan 50 AZN pul köçür")
    assert bank_state["status"] == "rejected"



def test_simulated_orders_need_confirmation():
    cases = [
        ("Wolt-dan yemək sifariş et", "ORDER_FOOD", "Chef Tantuni"),
        ("Chef Tantunidən yemək sifariş edirəm", "ORDER_FOOD", "Chef Tantuni"),
        ("Aptekdən kardiomaqnil sifariş et", "ORDER_PHARMACY", "Zəfəran Aptek"),
        ("Taksi çağır", "ORDER_TAXI", "Wolt Taxi"),
    ]
    for text, intent, vendor in cases:
        state = run_agent_workflow("user-1", text)
        assert state["intent"] == intent, text
        assert state["status"] == "needs_confirmation", text
        assert state["action_data"]["simulated"] is True
        assert state["action_data"]["order"]["vendor"] == vendor


def test_medicine_reminder_is_not_a_pharmacy_order():
    state = run_agent_workflow("user-1", "Sabah saat 10-da dərmanımı xatırlat")
    assert state["intent"] == "CREATE_REMINDER"
    assert "sabah saat 10:00" in state["response"].lower()


def test_greeting_and_unknown_never_ask_for_confirmation():
    greeting = run_agent_workflow("user-1", "Salam")
    assert greeting["intent"] == "GENERAL_QUESTION"
    assert greeting["status"] == "completed"
    assert greeting["response"].startswith("Salam!")

    unknown = run_agent_workflow("user-1", "bla bla qırmızı")
    assert unknown["status"] == "needs_clarification"

