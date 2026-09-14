"""Match scoring + improvement suggestions.

Suggestions use GPT (via OpenAI chat completions) for richer, more specific
feedback when OPENAI_API_KEY is configured. Without a key, falls back to a
transparent, deterministic rule-based suggestion engine - so the app is
always fully functional either way.
"""

from config import Config
from services.embedding_service import embed_text, cosine_similarity
from services.resume_parser import extract_skills


def compute_match(resume_text: str, resume_skills: list, resume_embedding: list, resume_embedding_source: str,
                   job_description: str, job_tags: list = None):
    job_tags = job_tags or []
    job_embedding, job_source = embed_text(job_description)

    if job_source != resume_embedding_source:
        raise ValueError(
            f"Resume was embedded with '{resume_embedding_source}' but the app is "
            f"currently using '{job_source}'. Re-upload the resume to refresh "
            "its embedding before analyzing it."
        )

    similarity = cosine_similarity(resume_embedding, job_embedding)
    match_score = round(max(0.0, similarity) * 100, 2)

    job_skills_from_text = set(extract_skills(job_description))
    job_skills = job_skills_from_text.union({t.lower() for t in job_tags})
    resume_skill_set = {s.lower() for s in resume_skills}

    matched_skills = sorted(job_skills & resume_skill_set)
    missing_skills = sorted(job_skills - resume_skill_set)

    if Config.USE_OPENAI:
        suggestions = _gpt_suggestions(resume_text, job_description, match_score, matched_skills, missing_skills)
    else:
        suggestions = _heuristic_suggestions(match_score, matched_skills, missing_skills, resume_text)

    return {
        "match_score": match_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "suggestions": suggestions,
        "suggestions_source": "openai" if Config.USE_OPENAI else "heuristic",
    }


def _gpt_suggestions(resume_text, job_description, match_score, matched_skills, missing_skills):
    from openai import OpenAI

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    prompt = f"""You are an expert technical resume coach. A candidate's resume has a
{match_score}% semantic match against a job description.

Matched skills: {', '.join(matched_skills) or 'none'}
Missing/gap skills: {', '.join(missing_skills) or 'none'}

RESUME (truncated):
{resume_text[:3000]}

JOB DESCRIPTION (truncated):
{job_description[:2000]}

Give 4-6 short, specific, actionable bullet points to improve this resume for
this specific job. Focus on: keyword/phrasing alignment, quantifiable
achievements, and structure. Do not restate the match score. Return ONLY a
JSON array of strings, nothing else."""

    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        content = response.choices[0].message.content.strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        import json

        suggestions = json.loads(content)
        if isinstance(suggestions, list) and suggestions:
            return suggestions
    except Exception:  # noqa: BLE001
        pass

    # Fall back silently if the GPT call/parsing fails for any reason
    return _heuristic_suggestions(match_score, matched_skills, missing_skills, resume_text)


def _heuristic_suggestions(match_score, matched_skills, missing_skills, resume_text):
    suggestions = []

    if missing_skills:
        top_missing = missing_skills[:8]
        suggestions.append(
            "Consider adding these relevant keywords/skills if you genuinely have "
            f"experience with them: {', '.join(top_missing)}."
        )

    if match_score < 40:
        suggestions.append(
            "Overall semantic alignment with this job description is low. Try "
            "rewriting your summary/experience bullets to mirror the language "
            "and priorities used in the job posting."
        )
    elif match_score < 70:
        suggestions.append(
            "Decent alignment, but there's room to better mirror the job "
            "description's terminology in your bullet points and summary."
        )
    else:
        suggestions.append("Strong semantic alignment with this job description.")

    word_count = len(resume_text.split())
    if word_count < 150:
        suggestions.append(
            "Your resume content looks quite short - consider adding more "
            "detail on measurable achievements and technologies used."
        )
    elif word_count > 1200:
        suggestions.append(
            "Your resume content is quite long - consider trimming to the "
            "most relevant, recent, and quantifiable experience."
        )

    if not any(char.isdigit() for char in resume_text):
        suggestions.append(
            "Add quantifiable metrics (%, $, time saved, users served, etc.) "
            "to strengthen the impact of your bullet points."
        )

    if matched_skills:
        suggestions.append(
            f"Good overlap on: {', '.join(matched_skills[:8])}. Make sure these "
            "appear near the top of your resume/summary for ATS keyword scanning."
        )

    return suggestions


def general_resume_feedback(resume_text: str, resume_skills: list):
    if Config.USE_OPENAI:
        try:
            return _gpt_general_feedback(resume_text)
        except Exception:  # noqa: BLE001
            pass
    return _heuristic_general_feedback(resume_text, resume_skills)


def _gpt_general_feedback(resume_text):
    from openai import OpenAI
    import json

    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    prompt = f"""You are an expert resume coach. Review this resume and give
4-6 short, specific, actionable improvement tips covering structure, impact/
metrics, clarity, and keyword strength. Return ONLY a JSON array of strings.

RESUME:
{resume_text[:3500]}"""

    response = client.chat.completions.create(
        model=Config.OPENAI_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    content = response.choices[0].message.content.strip()
    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    feedback = json.loads(content)
    if isinstance(feedback, list) and feedback:
        return feedback
    raise ValueError("empty feedback")


def _heuristic_general_feedback(resume_text, resume_skills):
    feedback = []

    word_count = len(resume_text.split())
    if word_count < 150:
        feedback.append("Resume is quite short. Aim for 300-700 words for a solid one-page resume.")
    if word_count > 1200:
        feedback.append("Resume is long. Consider condensing to the most relevant/recent 1-2 pages.")

    action_verbs = ["built", "led", "designed", "developed", "implemented", "optimized",
                     "created", "managed", "improved", "launched", "automated", "architected"]
    lowered = resume_text.lower()
    used_verbs = [v for v in action_verbs if v in lowered]
    if len(used_verbs) < 3:
        feedback.append(
            "Use more strong action verbs (e.g. built, led, optimized, designed) "
            "at the start of your bullet points."
        )

    if not any(char.isdigit() for char in resume_text):
        feedback.append("Add quantifiable results/metrics to your experience bullets.")

    if len(resume_skills) < 5:
        feedback.append("Consider explicitly listing more of your technical skills in a dedicated section.")

    if not feedback:
        feedback.append("Resume looks solid overall - well-structured with clear detail and skills.")

    return feedback
