import gradio as gr

from rcm_agent.memory import memory_store
from runtime import run_structured_claim


async def process_claim(
    patient_id: str,
    insurance_number: str,
    visit_reason: str,
    session_id: str,
):
    response = await run_structured_claim(
        patient_id=patient_id,
        insurance_number=insurance_number,
        visit_reason=visit_reason,
        session_id=session_id.strip() or None,
        user_id="gradio_user",
    )
    result = response.result
    summary = (
        f"### Claim result\n\n"
        f"- Session: `{response.session_id}`\n"
        f"- Status: `{result.status}`\n"
        f"- Codes: `{', '.join(result.codes) or 'None'}`\n"
        f"- Claim ID: `{result.claim_id or 'Not created'}`\n"
        f"- Audit score: `{result.issue_score}`\n"
        f"- Coding source: `{result.coding_source}`\n"
        f"- Retries: `{result.retry_count}`"
    )
    return (
        summary,
        result.appeal or "No appeal is needed.",
        result.model_dump(),
        memory_store.recent(5),
        response.session_id,
    )


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="Revenue Cycle Agent") as interface:
        gr.Markdown(
            "# Revenue Cycle Agent\n"
            "Reduce coding errors and claim delays through intake, coding, audit, appeal, and memory."
        )
        with gr.Row():
            with gr.Column():
                patient_id = gr.Textbox(label="Patient ID", value="P001")
                insurance = gr.Textbox(label="Insurance number", value="AET123456")
                reason = gr.Textbox(
                    label="Visit reason",
                    value="The patient has type 2 diabetes and high blood pressure.",
                    lines=3,
                )
                session = gr.Textbox(
                    label="Session ID",
                    placeholder="Leave empty for a new session",
                )
                run_button = gr.Button("Process claim", variant="primary")

            with gr.Column():
                summary = gr.Markdown()
                returned_session = gr.Textbox(label="Returned session ID")
                with gr.Tabs():
                    with gr.Tab("Appeal"):
                        appeal = gr.Textbox(lines=10)
                    with gr.Tab("Final state"):
                        state = gr.JSON()
                    with gr.Tab("Recent memory"):
                        memory = gr.JSON()

        run_button.click(
            process_claim,
            inputs=[patient_id, insurance, reason, session],
            outputs=[summary, appeal, state, memory, returned_session],
        )
    return interface


if __name__ == "__main__":
    build_interface().launch()
