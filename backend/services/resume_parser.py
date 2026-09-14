import io
import re
import unicodedata

import PyPDF2
import docx

SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "bash",
    "flask", "django", "fastapi", "node.js", "nodejs", "express", "spring",
    "spring boot", "rest api", "restful", "graphql", "html", "css", "react",
    "angular", "vue", "next.js", "redux", "tailwind",
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "pytorch", "tensorflow", "keras", "scikit-learn",
    "pandas", "numpy", "data analysis", "data science", "llm", "openai",
    "vector embeddings", "embeddings", "transformers", "huggingface",
    "langchain", "rag",
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "sqlite", "cassandra", "dynamodb",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "jenkins",
    "terraform", "git", "github", "gitlab", "linux",
    "agile", "scrum", "microservices", "unit testing", "tdd", "system design",
    "object oriented programming", "oop",
]


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def extract_text_from_pdf(file_stream) -> str:
    reader = PyPDF2.PdfReader(file_stream)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text_from_docx(file_stream) -> str:
    document = docx.Document(file_stream)
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[1].lower()
    stream = io.BytesIO(file_bytes)
    if ext == "pdf":
        return extract_text_from_pdf(stream)
    elif ext == "docx":
        return extract_text_from_docx(stream)
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {ext}")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_emails(text: str):
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(dict.fromkeys(re.findall(pattern, text)))


def extract_phones(text: str):
    pattern = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    matches = [m.group() for m in re.finditer(pattern, text)]
    cleaned = [m.strip() for m in matches if len(re.sub(r"\D", "", m)) >= 7]
    return list(dict.fromkeys(cleaned))[:5]


SKILL_ALIASES = {"postgres": "postgresql", "nodejs": "node.js", "golang": "go",
                 "natural language processing": "nlp", "embeddings": "vector embeddings"}
SKILL_PATTERNS = [(skill, re.compile(r"(?<!\w)" + re.escape(skill) + r"(?![\w+#])", re.IGNORECASE))
                  for skill in SKILL_KEYWORDS]


def extract_skills(text: str):
    return sorted({SKILL_ALIASES.get(skill, skill) for skill, pattern in SKILL_PATTERNS
                   if pattern.search(text)})


def parse_resume(file_bytes: bytes, filename: str):
    raw_text = extract_text(file_bytes, filename)
    cleaned = clean_text(raw_text)
    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned,
        "emails": extract_emails(cleaned),
        "phones": extract_phones(cleaned),
        "skills": extract_skills(cleaned),
    }
