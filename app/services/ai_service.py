"""AI Service - Groq API integration for note enhancement."""

import os
from groq import Groq


def get_groq_client():
    """Get Groq client with API key from environment."""
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in environment")
    return Groq(api_key=api_key)


def summarize_text(text):
    """
    Summarize text into bullet points using Groq AI.

    Args:
        text: The text content to summarize

    Returns:
        str: Bullet-point summary of the content
    """
    if not text or not text.strip():
        raise ValueError("No content to summarize")

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a helpful study assistant. Summarize the following notes into clear, concise bullet points.

Focus on:
- Key concepts and definitions
- Important facts and figures
- Main ideas and themes
- Relationships between concepts

Format your response as bullet points using - for each point.
Keep each bullet point concise but informative.
Group related points together if applicable."""
            },
            {
                "role": "user",
                "content": f"Please summarize these notes:\n\n{text}"
            }
        ],
        temperature=0.3,  # Lower temperature for more focused output
        max_tokens=1000
    )

    return response.choices[0].message.content


def expand_text(text, context=""):
    """
    Expand brief text into detailed explanations.

    Args:
        text: The brief text to expand
        context: Optional surrounding context

    Returns:
        str: Expanded, detailed explanation
    """
    if not text or not text.strip():
        raise ValueError("No content to expand")

    client = get_groq_client()

    prompt = f"Please expand on this text with more details, examples, and explanations:\n\n{text}"
    if context:
        prompt = f"Context from the notes:\n{context}\n\n{prompt}"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a helpful study assistant. Expand the given text with:
- Detailed explanations
- Examples and illustrations
- Definitions of key terms
- Connections to related concepts

Write in a clear, educational style suitable for study notes."""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5,
        max_tokens=1500
    )

    return response.choices[0].message.content


def cleanup_text(text):
    """
    Clean up text and apply smart formatting (headers, bullets, bold, colors).

    Args:
        text: The text to clean up and format

    Returns:
        str: HTML-formatted text with proper structure and color coding
    """
    if not text or not text.strip():
        raise ValueError("No content to clean up")

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a note formatting assistant. Your job is to clean up and format notes into well-structured, visually appealing HTML using Notion's color palette.

Tasks:
1. Fix spelling and grammar errors
2. Improve sentence structure and clarity
3. Apply smart formatting with Notion's colors:

HEADERS (color-coded by level):
- <h1 style="color: #0b6e99;"> for main titles (blue)
- <h2 style="color: #6940a5;"> for section headers (purple)
- <h3 style="color: #0f7b6c;"> for sub-section headers (green)

LISTS:
- <ul><li> for bullet point lists
- <ol><li> for numbered lists/steps

TEXT COLORS (use these for important terms):
- <span style="color: #e03e3e;"> for key terms, warnings (red)
- <span style="color: #d9730d;"> for important concepts (orange)
- <span style="color: #0b6e99;"> for definitions (blue)
- <span style="color: #0f7b6c;"> for examples (green)
- <span style="color: #6940a5;"> for special terms (purple)

BACKGROUND HIGHLIGHTS (use sparingly for critical info):
- <span style="background-color: #fbf3db;"> for definitions, key formulas (yellow)
- <span style="background-color: #edf3ec;"> for examples, tips (green)
- <span style="background-color: #fdebec;"> for warnings, important (red)
- <span style="background-color: #e7f3f8;"> for references (blue)
- <span style="background-color: #f4f0f7;"> for special notes (purple)

OTHER ELEMENTS:
- <p> for paragraphs
- <strong> for bold text (use with colors above)
- <blockquote style="border-left: 4px solid #6940a5; padding-left: 1rem; color: #64473a;"> for quotes or callouts

Formatting rules:
- If a line looks like a title, make it a header with appropriate color
- Bullet points for lists, numbered for steps/sequences
- Use colored text for important terms and vocabulary
- Use background highlights sparingly for truly critical information
- Keep original meaning intact, don't add content
- Make the notes visually scannable and study-friendly

Return ONLY the formatted HTML, no explanations or markdown."""
            },
            {
                "role": "user",
                "content": f"Format these notes:\n\n{text}"
            }
        ],
        temperature=0.2,
        max_tokens=3000
    )

    return response.choices[0].message.content


def generate_flashcards(text, num_cards=10):
    """
    Generate flashcards from text content.

    Args:
        text: The text content to generate flashcards from
        num_cards: Target number of flashcards to generate

    Returns:
        list: List of dictionaries with 'front' and 'back' keys
    """
    if not text or not text.strip():
        raise ValueError("No content to generate flashcards from")

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""You are a study assistant that creates flashcards from notes. Generate {num_cards} flashcards from the provided content.

Rules:
1. Focus on key terms, definitions, concepts, and important facts
2. Front should be a question or term
3. Back should be a concise answer or definition
4. Make cards that test understanding, not just memorization
5. Cover the most important concepts from the content

Return ONLY a JSON array of flashcards in this exact format:
[
  {{"front": "What is X?", "back": "X is..."}},
  {{"front": "Define Y", "back": "Y is defined as..."}}
]

No explanations, no markdown, just the JSON array."""
            },
            {
                "role": "user",
                "content": f"Generate flashcards from these notes:\n\n{text}"
            }
        ],
        temperature=0.3,
        max_tokens=2000
    )

    import json
    result = response.choices[0].message.content.strip()

    # Clean up response if needed
    if result.startswith('```'):
        result = result.split('```')[1]
        if result.startswith('json'):
            result = result[4:]
        result = result.strip()

    try:
        cards = json.loads(result)
        return cards
    except json.JSONDecodeError:
        raise ValueError("Failed to parse AI response as flashcards")


def transform_text(text, action):
    """
    Transform text based on the specified action.

    Args:
        text: The text to transform
        action: One of 'improve', 'proofread', 'simplify', 'shorter', 'longer', 'formal', 'casual'

    Returns:
        str: Transformed text
    """
    if not text or not text.strip():
        raise ValueError("No text to transform")

    prompts = {
        'improve': "Improve this writing. Make it clearer, more engaging, and better structured. Keep the same meaning and tone.",
        'proofread': "Proofread this text. Fix any spelling, grammar, and punctuation errors. Keep the original meaning intact.",
        'simplify': "Simplify this text. Use simpler words and shorter sentences. Make it easier to understand while keeping the meaning.",
        'shorter': "Make this text shorter and more concise. Remove unnecessary words and keep only the essential information.",
        'longer': "Expand this text with more details, examples, and explanations. Make it more comprehensive.",
        'formal': "Rewrite this text in a more formal, professional tone. Use proper language and avoid casual expressions.",
        'casual': "Rewrite this text in a more casual, conversational tone. Make it friendly and approachable."
    }

    if action not in prompts:
        raise ValueError(f"Unknown action: {action}")

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"{prompts[action]}\n\nReturn ONLY the transformed text, nothing else. No explanations, no quotes around it."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        temperature=0.3,
        max_tokens=2000
    )

    return response.choices[0].message.content


def generate_study_guide(notes_content, class_name="", focus_areas=None):
    """
    Generate a comprehensive study guide from multiple notes.

    Args:
        notes_content: Combined content from multiple notes
        class_name: Name of the class for context
        focus_areas: Optional list of areas to focus on

    Returns:
        str: HTML-formatted study guide
    """
    if not notes_content or not notes_content.strip():
        raise ValueError("No content to generate study guide from")

    client = get_groq_client()

    focus_prompt = ""
    if focus_areas:
        focus_prompt = f"\n\nPay special attention to these topics: {', '.join(focus_areas)}"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""You are an expert study guide creator. Create a comprehensive, well-organized study guide from the provided notes for {class_name or 'this class'}.{focus_prompt}

Your study guide should include:

1. **Overview Section**
   - Brief summary of the main topics covered
   - Learning objectives

2. **Key Concepts & Definitions**
   - Important terms and their definitions
   - Core concepts explained clearly

3. **Important Points**
   - Main ideas and takeaways
   - Critical information to remember

4. **Relationships & Connections**
   - How concepts relate to each other
   - Cause and effect relationships

5. **Quick Reference**
   - Formulas, dates, or facts to memorize
   - Summary tables if applicable

6. **Review Questions**
   - Self-test questions to check understanding
   - Critical thinking questions

Format your response as clean HTML:
- <h1 style="color: #0b6e99;"> for the study guide title
- <h2 style="color: #6940a5;"> for main sections
- <h3 style="color: #0f7b6c;"> for subsections
- <ul> and <li> for lists
- <strong style="color: #d9730d;"> for key terms
- <span style="background-color: #fbf3db; padding: 2px 6px; border-radius: 3px;"> for definitions
- <blockquote style="border-left: 4px solid #6940a5; padding-left: 1rem; margin: 1rem 0; background: #f8f9fa;"> for important notes

Make the study guide scannable, organized, and exam-ready."""
            },
            {
                "role": "user",
                "content": f"Create a study guide from these notes:\n\n{notes_content}"
            }
        ],
        temperature=0.3,
        max_tokens=4000
    )

    return response.choices[0].message.content


def generate_quiz(text, num_questions=10, question_types=None):
    """
    Generate quiz questions from text content.

    Args:
        text: The text content to generate questions from
        num_questions: Number of questions to generate
        question_types: List of question types ('multiple_choice', 'true_false', 'short_answer')

    Returns:
        list: List of question dictionaries
    """
    if not text or not text.strip():
        raise ValueError("No content to generate quiz from")

    if question_types is None:
        question_types = ['multiple_choice', 'true_false']

    types_str = ', '.join(question_types)

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""You are a quiz generator. Generate {num_questions} quiz questions from the provided content.

Question types to include: {types_str}

Return a JSON array of questions with this format:
[
  {{
    "type": "multiple_choice",
    "question": "What is...?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": 0,
    "explanation": "Brief explanation of why this is correct"
  }},
  {{
    "type": "true_false",
    "question": "Statement to evaluate",
    "correct_answer": true,
    "explanation": "Brief explanation"
  }},
  {{
    "type": "short_answer",
    "question": "Question requiring written response",
    "correct_answer": "Expected key points in answer",
    "explanation": "What a good answer should include"
  }}
]

Rules:
1. Questions should test understanding, not just memorization
2. Multiple choice should have 4 options with only one correct answer
3. Include a mix of difficulty levels
4. Explanations should be educational
5. correct_answer for multiple_choice is the index (0-3)
6. correct_answer for true_false is true or false
7. correct_answer for short_answer is the expected answer

Return ONLY the JSON array, no explanations."""
            },
            {
                "role": "user",
                "content": f"Generate quiz questions from this content:\n\n{text}"
            }
        ],
        temperature=0.4,
        max_tokens=3000
    )

    import json
    result = response.choices[0].message.content.strip()

    # Clean up response if needed
    if result.startswith('```'):
        result = result.split('```')[1]
        if result.startswith('json'):
            result = result[4:]
        result = result.strip()

    try:
        questions = json.loads(result)
        return questions
    except json.JSONDecodeError:
        raise ValueError("Failed to parse AI response as quiz questions")


def chat_with_tutor(message, context_notes=None, conversation_history=None, class_name=None):
    """
    Chat with an AI tutor about study materials.

    Args:
        message: The user's message/question
        context_notes: Optional list of note contents to provide context
        conversation_history: Optional list of previous messages [{'role': 'user'|'assistant', 'content': '...'}]
        class_name: Optional class name for context

    Returns:
        str: The AI tutor's response
    """
    if not message or not message.strip():
        raise ValueError("No message provided")

    client = get_groq_client()

    # Build context from notes
    context_prompt = ""
    if context_notes:
        context_prompt = "\n\nRelevant study materials:\n"
        for i, note in enumerate(context_notes[:5], 1):  # Limit to 5 notes
            content = note.get('content', '')[:2000]  # Limit content length
            title = note.get('title', f'Note {i}')
            context_prompt += f"\n--- {title} ---\n{content}\n"

    class_context = f" for {class_name}" if class_name else ""

    system_prompt = f"""You are an expert AI study tutor{class_context}. Your role is to help students understand their study materials, answer questions, explain concepts, and assist with learning.

Guidelines:
1. Be encouraging and supportive
2. Explain concepts clearly and at the right level
3. Use examples and analogies when helpful
4. If the student's question relates to their notes, reference them
5. Ask clarifying questions if needed
6. Suggest study strategies when appropriate
7. Be concise but thorough
8. If you don't know something, admit it honestly{context_prompt}"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (limit to last 10 messages)
    if conversation_history:
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', '')
            })

    # Add current message
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.7,
        max_tokens=1500
    )

    return response.choices[0].message.content


def grade_short_answer(question, expected_answer, user_answer):
    """
    Grade a short answer question using AI.

    Args:
        question: The original question
        expected_answer: The expected/correct answer
        user_answer: The student's answer

    Returns:
        dict: {'score': 0-100, 'feedback': str, 'is_correct': bool}
    """
    if not user_answer or not user_answer.strip():
        return {
            'score': 0,
            'feedback': 'No answer provided.',
            'is_correct': False
        }

    client = get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are an expert grader. Grade the student's answer to the question.

Compare the student's answer to the expected answer and provide:
1. A score from 0-100
2. Brief feedback explaining the score
3. Whether the answer is essentially correct (true/false)

Consider partial credit for partially correct answers.
Be fair but not overly strict - focus on understanding of key concepts.

Return ONLY a JSON object in this format:
{"score": 85, "feedback": "Good explanation of the concept, but missed X detail.", "is_correct": true}

No explanations outside the JSON."""
            },
            {
                "role": "user",
                "content": f"""Question: {question}

Expected Answer: {expected_answer}

Student's Answer: {user_answer}

Grade this answer:"""
            }
        ],
        temperature=0.2,
        max_tokens=300
    )

    import json
    result = response.choices[0].message.content.strip()

    # Clean up response if needed
    if result.startswith('```'):
        result = result.split('```')[1]
        if result.startswith('json'):
            result = result[4:]
        result = result.strip()

    try:
        grading = json.loads(result)
        return {
            'score': grading.get('score', 0),
            'feedback': grading.get('feedback', ''),
            'is_correct': grading.get('is_correct', False)
        }
    except json.JSONDecodeError:
        # Fallback to simple matching if AI fails
        if user_answer.lower().strip() in expected_answer.lower():
            return {'score': 80, 'feedback': 'Answer appears correct.', 'is_correct': True}
        return {'score': 0, 'feedback': 'Could not evaluate answer.', 'is_correct': False}
