"""
Quiz Service - Handles MCQ quiz generation and evaluation for ProfAI
"""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from services.llm_service import LLMService
from models.schemas import Quiz, QuizQuestion, QuizSubmission, QuizResult, QuizDisplay, QuizQuestionDisplay
import config

class QuizService:
    """Service for generating and evaluating MCQ quizzes."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.quiz_storage_dir = os.path.join(os.path.dirname(__file__), "..", "data", "quizzes")
        self.answers_storage_dir = os.path.join(os.path.dirname(__file__), "..", "data", "quiz_answers")
        
        # Ensure storage directories exist
        os.makedirs(self.quiz_storage_dir, exist_ok=True)
        os.makedirs(self.answers_storage_dir, exist_ok=True)
        
        logging.info("QuizService initialized")
    
    async def generate_module_quiz(self, module_week: int, course_content: dict) -> Quiz:
        """Generate a 20-question MCQ quiz for a specific module."""
        try:
            # Find the specific module
            module = None
            for mod in course_content.get("modules", []):
                if mod.get("week") == module_week:
                    module = mod
                    break
            
            if not module:
                raise ValueError(f"Module week {module_week} not found in course content")
            
            # Extract content for the module
            module_content = self._extract_module_content(module)
            
            # Generate quiz using LLM
            quiz_id = f"module_{module_week}_{uuid.uuid4().hex[:8]}"
            
            logging.info(f"Generating 20-question quiz for module week {module_week}")
            
            quiz_prompt = self._create_module_quiz_prompt(module, module_content)
            
            # Try to generate quiz with retry logic
            quiz_response = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logging.info(f"Quiz generation attempt {attempt + 1}/{max_retries}")
                    quiz_response = await self.llm_service.generate_response(quiz_prompt, temperature=0.7)
                    if quiz_response and len(quiz_response.strip()) > 100:  # Basic validation
                        break
                except Exception as e:
                    logging.warning(f"Quiz generation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # Use fallback quiz on final failure
                        quiz_response = self._generate_fallback_quiz(module_content, 20)
            
            if not quiz_response:
                raise ValueError("Failed to generate quiz after all attempts")
            
            # Parse the LLM response into structured quiz
            questions = self._parse_quiz_response(quiz_response, quiz_id)
            
            # Ensure we have exactly 20 questions
            if len(questions) < 20:
                # Generate additional questions if needed
                additional_prompt = self._create_additional_questions_prompt(module_content, 20 - len(questions))
                additional_response = await self.llm_service.generate_response(additional_prompt, temperature=0.7)
                additional_questions = self._parse_quiz_response(additional_response, quiz_id, start_id=len(questions))
                questions.extend(additional_questions)
            
            # Take only first 20 questions
            questions = questions[:20]
            
            quiz = Quiz(
                quiz_id=quiz_id,
                title=f"Module {module_week} Quiz: {module.get('title', 'Module Quiz')}",
                description=f"20-question MCQ quiz covering content from Week {module_week}",
                questions=questions,
                total_questions=len(questions),
                quiz_type="module",
                module_week=module_week
            )
            
            # Store quiz and answers
            self._store_quiz(quiz)
            
            logging.info(f"Generated module quiz with {len(questions)} questions")
            return quiz
            
        except Exception as e:
            logging.error(f"Error generating module quiz: {e}")
            raise e
    
    async def generate_course_quiz(self, course_content: dict) -> Quiz:
        """Generate a 40-question MCQ quiz covering the entire course."""
        try:
            # Extract content from all modules
            all_content = self._extract_all_course_content(course_content)
            
            quiz_id = f"course_{uuid.uuid4().hex[:8]}"
            
            logging.info("Generating 40-question course quiz")
            
            # Generate quiz using LLM in chunks with retry logic
            questions_1 = []
            questions_2 = []
            
            # Part 1 - First 20 questions
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    logging.info(f"Generating part 1 - attempt {attempt + 1}/{max_retries}")
                    quiz_prompt_1 = self._create_course_quiz_prompt(all_content, part=1)
                    quiz_response_1 = await self.llm_service.generate_response(quiz_prompt_1, temperature=0.7)
                    if quiz_response_1 and len(quiz_response_1.strip()) > 100:
                        questions_1 = self._parse_quiz_response(quiz_response_1, quiz_id, start_id=0)
                        break
                except Exception as e:
                    logging.warning(f"Part 1 generation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # Use fallback for part 1
                        fallback_response = self._generate_fallback_quiz(all_content[:4000], 20)
                        questions_1 = self._parse_quiz_response(fallback_response, quiz_id, start_id=0)
            
            # Part 2 - Second 20 questions
            for attempt in range(max_retries):
                try:
                    logging.info(f"Generating part 2 - attempt {attempt + 1}/{max_retries}")
                    quiz_prompt_2 = self._create_course_quiz_prompt(all_content, part=2)
                    quiz_response_2 = await self.llm_service.generate_response(quiz_prompt_2, temperature=0.7)
                    if quiz_response_2 and len(quiz_response_2.strip()) > 100:
                        questions_2 = self._parse_quiz_response(quiz_response_2, quiz_id, start_id=20)
                        break
                except Exception as e:
                    logging.warning(f"Part 2 generation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # Use fallback for part 2
                        fallback_response = self._generate_fallback_quiz(all_content[4000:], 20)
                        questions_2 = self._parse_quiz_response(fallback_response, quiz_id, start_id=20)
            
            # Combine all questions
            all_questions = questions_1 + questions_2
            
            # Validate we have enough questions
            if len(all_questions) < 10:  # Minimum threshold
                raise ValueError(f"Generated insufficient questions: {len(all_questions)}. Quiz generation failed.")
            
            # Take exactly 40 questions (or as many as we have)
            all_questions = all_questions[:40]
            
            quiz = Quiz(
                quiz_id=quiz_id,
                title=f"Final Course Quiz: {course_content.get('course_title', 'Course Quiz')}",
                description=f"{len(all_questions)}-question comprehensive MCQ quiz covering the entire course content",
                questions=all_questions,
                total_questions=len(all_questions),
                quiz_type="course",
                module_week=None
            )
            
            # Store quiz and answers
            self._store_quiz(quiz)
            
            logging.info(f"Generated course quiz with {len(all_questions)} questions")
            return quiz
            
        except Exception as e:
            logging.error(f"Error generating course quiz: {e}")
            raise e
    
    def evaluate_quiz(self, submission: QuizSubmission) -> QuizResult:
        """Evaluate a quiz submission and return results."""
        try:
            # Load quiz and answers
            quiz_data = self._load_quiz_answers(submission.quiz_id)
            if not quiz_data:
                raise ValueError(f"Quiz {submission.quiz_id} not found")
            
            correct_answers = quiz_data["answers"]
            quiz_info = quiz_data["quiz"]
            
            # Calculate score
            score = 0
            detailed_results = []
            
            for question_id, user_answer in submission.answers.items():
                is_correct = user_answer.upper() == correct_answers.get(question_id, "").upper()
                if is_correct:
                    score += 1
                
                detailed_results.append({
                    "question_id": question_id,
                    "user_answer": user_answer.upper(),
                    "correct_answer": correct_answers.get(question_id, ""),
                    "is_correct": is_correct
                })
            
            total_questions = len(correct_answers)
            percentage = (score / total_questions) * 100 if total_questions > 0 else 0
            passed = percentage >= 60.0
            
            result = QuizResult(
                quiz_id=submission.quiz_id,
                user_id=submission.user_id,
                score=score,
                total_questions=total_questions,
                percentage=round(percentage, 2),
                passed=passed,
                detailed_results=detailed_results
            )
            
            # Store submission result
            self._store_submission_result(submission, result)
            
            logging.info(f"Evaluated quiz {submission.quiz_id}: {score}/{total_questions} ({percentage:.1f}%)")
            return result
            
        except Exception as e:
            logging.error(f"Error evaluating quiz: {e}")
            raise e
    
    def get_quiz_without_answers(self, quiz_id: str) -> Optional[QuizDisplay]:
        """Get quiz for display (without correct answers)."""
        try:
            quiz_file = os.path.join(self.quiz_storage_dir, f"{quiz_id}.json")
            if not os.path.exists(quiz_file):
                return None
            
            with open(quiz_file, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)
            
            # Create display questions without correct answers
            display_questions = []
            for question in quiz_data["questions"]:
                display_questions.append(QuizQuestionDisplay(
                    question_id=question["question_id"],
                    question_text=question["question_text"],
                    options=question["options"],
                    topic=question.get("topic", "")
                ))
            
            # Create display quiz
            display_quiz = QuizDisplay(
                quiz_id=quiz_data["quiz_id"],
                title=quiz_data["title"],
                description=quiz_data["description"],
                questions=display_questions,
                total_questions=quiz_data["total_questions"],
                quiz_type=quiz_data["quiz_type"],
                module_week=quiz_data.get("module_week")
            )
            
            return display_quiz
            
        except Exception as e:
            logging.error(f"Error loading quiz {quiz_id}: {e}")
            return None
    
    def _extract_module_content(self, module: dict) -> str:
        """Extract text content from a module."""
        content_parts = [f"Module Week {module.get('week')}: {module.get('title', '')}"]
        
        for sub_topic in module.get("sub_topics", []):
            content_parts.append(f"\n--- {sub_topic.get('title', '')} ---")
            content_parts.append(sub_topic.get('content', ''))
        
        return "\n".join(content_parts)
    
    def _extract_all_course_content(self, course_content: dict) -> str:
        """Extract text content from entire course."""
        content_parts = [f"Course: {course_content.get('course_title', '')}"]
        
        for module in course_content.get("modules", []):
            content_parts.append(self._extract_module_content(module))
        
        return "\n".join(content_parts)
    
    def _create_module_quiz_prompt(self, module: dict, content: str) -> str:
        """Create prompt for module quiz generation."""
        return f"""Generate a 20-question multiple choice quiz based on the following module content.

MODULE INFORMATION:
Week: {module.get('week')}
Title: {module.get('title', '')}

CONTENT:
{content}

REQUIREMENTS:
1. Generate exactly 20 multiple choice questions
2. Each question should have 4 options (A, B, C, D)
3. Questions should cover different aspects of the module content
4. Mix difficulty levels: 40% easy, 40% medium, 20% hard
5. Include practical application questions
6. Ensure questions test understanding, not just memorization

FORMAT YOUR RESPONSE AS:
Q1. [Question text]
A) [Option A]
B) [Option B] 
C) [Option C]
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]

Q2. [Next question...]

Continue this format for all 20 questions."""
    
    def _create_course_quiz_prompt(self, content: str, part: int) -> str:
        """Create prompt for course quiz generation."""
        question_range = f"questions {1 + (part-1)*20} to {part*20}" if part == 1 else f"questions 21 to 40"
        
        return f"""Generate {question_range} of a comprehensive multiple choice quiz based on the entire course content below.

COURSE CONTENT:
{content[:8000]}  # Limit content to avoid token limits

REQUIREMENTS:
1. Generate exactly 20 multiple choice questions for this part
2. Each question should have 4 options (A, B, C, D)
3. Cover content from all modules proportionally
4. Mix difficulty levels: 30% easy, 50% medium, 20% hard
5. Include synthesis questions that connect concepts across modules
6. Test both theoretical understanding and practical application

FORMAT YOUR RESPONSE AS:
Q{1 + (part-1)*20}. [Question text]
A) [Option A]
B) [Option B]
C) [Option C] 
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]

Continue this format for all 20 questions in this part."""
    
    def _create_additional_questions_prompt(self, content: str, num_questions: int) -> str:
        """Create prompt for generating additional questions."""
        return f"""Generate {num_questions} additional multiple choice questions based on the following content:

{content}

REQUIREMENTS:
1. Generate exactly {num_questions} questions
2. Each question should have 4 options (A, B, C, D)
3. Focus on different aspects not covered in previous questions
4. Maintain good difficulty distribution

FORMAT YOUR RESPONSE AS:
Q. [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]"""
    
    def _parse_quiz_response(self, response: str, quiz_id: str, start_id: int = 0) -> List[QuizQuestion]:
        """Parse LLM response into structured quiz questions."""
        questions = []
        lines = response.split('\n')
        
        current_question = {}
        question_count = start_id
        
        for line in lines:
            line = line.strip()
            
            # Question line
            if line.startswith('Q') and ('.' in line or ')' in line):
                if current_question and 'question_text' in current_question:
                    # Save previous question
                    questions.append(self._create_question_object(current_question, quiz_id, question_count))
                    question_count += 1
                
                # Start new question
                current_question = {}
                # Extract question text after Q1., Q2., etc.
                question_text = line.split('.', 1)[-1].strip() if '.' in line else line.split(')', 1)[-1].strip()
                current_question['question_text'] = question_text
                current_question['options'] = []
            
            # Option lines
            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                if 'options' in current_question:
                    option_text = line[2:].strip()  # Remove "A)" prefix
                    current_question['options'].append(option_text)
            
            # Answer line
            elif line.startswith('ANSWER:'):
                answer = line.replace('ANSWER:', '').strip().upper()
                current_question['correct_answer'] = answer
            
            # Explanation line
            elif line.startswith('EXPLANATION:'):
                explanation = line.replace('EXPLANATION:', '').strip()
                current_question['explanation'] = explanation
        
        # Don't forget the last question
        if current_question and 'question_text' in current_question:
            questions.append(self._create_question_object(current_question, quiz_id, question_count))
        
        return questions
    
    def _create_question_object(self, question_data: dict, quiz_id: str, question_num: int) -> QuizQuestion:
        """Create a QuizQuestion object from parsed data."""
        return QuizQuestion(
            question_id=f"{quiz_id}_q{question_num + 1}",
            question_text=question_data.get('question_text', ''),
            options=question_data.get('options', [])[:4],  # Ensure max 4 options
            correct_answer=question_data.get('correct_answer', 'A'),
            explanation=question_data.get('explanation', ''),
            topic=question_data.get('topic', '')
        )
    
    def _store_quiz(self, quiz: Quiz):
        """Store quiz and answers separately."""
        try:
            # Store full quiz data
            quiz_file = os.path.join(self.quiz_storage_dir, f"{quiz.quiz_id}.json")
            with open(quiz_file, 'w', encoding='utf-8') as f:
                json.dump(quiz.dict(), f, indent=2, ensure_ascii=False)
            
            # Store answers separately for evaluation
            answers = {}
            for question in quiz.questions:
                answers[question.question_id] = question.correct_answer
            
            answer_data = {
                "quiz_id": quiz.quiz_id,
                "answers": answers,
                "quiz": {
                    "title": quiz.title,
                    "total_questions": quiz.total_questions,
                    "quiz_type": quiz.quiz_type,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            answer_file = os.path.join(self.answers_storage_dir, f"{quiz.quiz_id}_answers.json")
            with open(answer_file, 'w', encoding='utf-8') as f:
                json.dump(answer_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Stored quiz {quiz.quiz_id} and answers")
            
        except Exception as e:
            logging.error(f"Error storing quiz: {e}")
            raise e
    
    def _load_quiz_answers(self, quiz_id: str) -> Optional[dict]:
        """Load quiz answers for evaluation."""
        try:
            answer_file = os.path.join(self.answers_storage_dir, f"{quiz_id}_answers.json")
            if not os.path.exists(answer_file):
                return None
            
            with open(answer_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logging.error(f"Error loading quiz answers: {e}")
            return None
    
    def _store_submission_result(self, submission: QuizSubmission, result: QuizResult):
        """Store quiz submission and result."""
        try:
            submission_data = {
                "submission": submission.dict(),
                "result": result.dict(),
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            submission_file = os.path.join(
                self.answers_storage_dir, 
                f"{submission.quiz_id}_{submission.user_id}_submission.json"
            )
            
            with open(submission_file, 'w', encoding='utf-8') as f:
                json.dump(submission_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Stored submission result for user {submission.user_id}")
            
        except Exception as e:
            logging.error(f"Error storing submission result: {e}")
    
    def _generate_fallback_quiz(self, content: str, num_questions: int) -> str:
        """Generate a simple fallback quiz when LLM fails."""
        logging.info(f"Using fallback quiz generation for {num_questions} questions")
        
        # Create basic questions from content keywords
        fallback_questions = []
        
        # Extract key topics from content
        content_lines = content.split('\n')
        topics = []
        for line in content_lines:
            if line.strip() and len(line.strip()) > 20:
                topics.append(line.strip()[:100])  # First 100 chars of meaningful lines
        
        # Generate basic questions
        for i in range(min(num_questions, len(topics), 10)):  # Max 10 fallback questions
            topic = topics[i] if i < len(topics) else "General Knowledge"
            
            fallback_questions.append(f"""Q{i+1}. What is the main concept discussed in: "{topic[:50]}..."?
A) Primary concept explanation
B) Secondary concept explanation  
C) Alternative explanation
D) Incorrect explanation
ANSWER: A
EXPLANATION: This question covers the main concept from the content.""")
        
        # Fill remaining with general questions if needed
        while len(fallback_questions) < min(num_questions, 10):
            q_num = len(fallback_questions) + 1
            fallback_questions.append(f"""Q{q_num}. Which of the following best describes the key learning objective?
A) Understanding core concepts
B) Memorizing facts only
C) Ignoring practical applications
D) Avoiding critical thinking
ANSWER: A
EXPLANATION: Learning focuses on understanding core concepts.""")
        
        return '\n\n'.join(fallback_questions)
