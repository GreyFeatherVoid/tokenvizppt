from html import escape


def build_slide_plan(topic: str, brief: str, page_count: int) -> list[dict[str, str]]:
    canonical = [
        ("Context", "Frame the audience, problem, and why this deck matters now."),
        ("Insight", "Summarize the strongest signal, constraint, or market change."),
        ("Strategy", "Show the recommended direction and the tradeoffs behind it."),
        ("Execution", "Turn the strategy into concrete steps and ownership."),
        ("Outcome", "Define the expected result, metrics, and next decision."),
    ]
    slides: list[dict[str, str]] = []
    for index in range(page_count):
        label, description = canonical[index % len(canonical)]
        slides.append(
            {
                "title": f"{index + 1}. {label}: {topic}",
                "summary": description,
                "detail": brief,
            }
        )
    return slides


def render_slide_html(args: dict[str, str | int]) -> str:
    page_number = int(args["page_number"])
    total_pages = int(args["total_pages"])
    title = escape(str(args["title"]))
    summary = escape(str(args["summary"]))
    detail = escape(str(args["detail"]))
    topic = escape(str(args["topic"]))

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {{
        color: #213022;
        background: #f4ead6;
        font-family: Georgia, 'Times New Roman', serif;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at 12% 15%, rgba(181, 92, 47, 0.28), transparent 31%),
          radial-gradient(circle at 86% 18%, rgba(44, 78, 52, 0.22), transparent 34%),
          linear-gradient(135deg, #f8f0df, #dfcfad);
      }}
      .slide {{
        width: min(1120px, 94vw);
        aspect-ratio: 16 / 9;
        display: grid;
        grid-template-rows: auto 1fr auto;
        gap: 28px;
        padding: 56px;
        border: 1px solid rgba(33, 48, 34, 0.16);
        border-radius: 34px;
        background: rgba(255, 251, 241, 0.78);
        box-shadow: 0 30px 90px rgba(43, 36, 24, 0.18);
        overflow: hidden;
      }}
      .kicker {{
        display: flex;
        justify-content: space-between;
        color: #a8512e;
        font-size: 15px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }}
      h1 {{
        max-width: 900px;
        margin: 0;
        font-size: clamp(42px, 6vw, 78px);
        line-height: 0.93;
        letter-spacing: -0.06em;
      }}
      .content {{
        display: grid;
        grid-template-columns: 1fr 0.72fr;
        gap: 36px;
        align-items: end;
      }}
      .summary {{
        margin: 0;
        color: #344834;
        font-size: clamp(22px, 2.4vw, 34px);
        line-height: 1.16;
      }}
      .detail {{
        padding: 24px;
        border-radius: 24px;
        background: #2d4d35;
        color: #fff4df;
        font-size: 18px;
        line-height: 1.45;
      }}
      .footer {{
        display: flex;
        justify-content: space-between;
        color: #64705c;
        font-size: 15px;
      }}
    </style>
  </head>
  <body>
    <article class="slide">
      <header class="kicker">
        <span>tokenvizPPT</span>
        <span>{page_number:02d}/{total_pages:02d}</span>
      </header>
      <section class="content">
        <div>
          <h1>{title}</h1>
          <p class="summary">{summary}</p>
        </div>
        <div class="detail">{detail}</div>
      </section>
      <footer class="footer">
        <span>{topic}</span>
        <span>Generated HTML slide</span>
      </footer>
    </article>
  </body>
</html>
"""
