from app.services.llm import generate_answer

context = [{
    "text": "Oracle Corporation\nMay – July 2025\nSummer Intern\n• Debugged and resolved HTTP/2 protocol stream violation bugs in Oracle HTTP Server caused by stream ID regression.\n• Fixed improper header and data frame transmissions on closed streams, improving protocol compliance.",
    "source": "demo_resume.pdf",
    "page": 1,
}]

for q in ["What does the document say about Oracle Corporation?", "What did they do at Oracle Corporation?", "Oracle Corporation"]:
    print(f"\n--- Q: {q} ---")
    print("".join(generate_answer(q, context, mode="specific")))