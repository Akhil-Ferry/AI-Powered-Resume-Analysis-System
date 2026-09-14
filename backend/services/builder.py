FIELDS = ("name", "headline", "email", "phone", "location", "summary", "skills",
          "experience", "education", "projects")


def build_resume(profile):
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object.")
    cleaned = {}
    for key in FIELDS:
        value = profile.get(key, "")
        if not isinstance(value, str) or len(value) > 10000:
            raise ValueError(f"{key} must be text, at most 10000 characters.")
        cleaned[key] = value.strip()
    if not cleaned["name"]:
        raise ValueError("Your name is required.")
    if not any(cleaned[key] for key in ("experience", "projects", "education")):
        raise ValueError("Add experience, projects or education.")
    lines = [cleaned["name"]]
    if cleaned["headline"]:
        lines.append(cleaned["headline"])
    contact = " | ".join(cleaned[k] for k in ("email", "phone", "location") if cleaned[k])
    if contact:
        lines.append(contact)
    for key in ("summary", "skills", "experience", "projects", "education"):
        if cleaned[key]:
            lines.extend(["", key.upper(), cleaned[key]])
    return "\n".join(lines), cleaned
