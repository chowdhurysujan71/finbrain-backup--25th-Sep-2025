"""
Simple math-based CAPTCHA system for preventing automated abuse
"""
import random
import hashlib
import time
import logging
from typing import Dict, Tuple, Optional
from flask import session

logger = logging.getLogger(__name__)

class MathCaptcha:
    """Simple math-based CAPTCHA for authentication endpoints"""
    
    def __init__(self):
        self.operations = ['+', '-', '*']
        self.max_number = 20  # Keep numbers manageable for users
        
    def generate_captcha(self) -> Dict[str, str]:
        """
        Generate a simple math problem for CAPTCHA
        
        Returns:
            Dict with question and encrypted answer
        """
        try:
            # Generate two random numbers
            num1 = random.randint(1, self.max_number)
            num2 = random.randint(1, self.max_number)
            operation = random.choice(self.operations)
            
            # Calculate answer
            if operation == '+':
                answer = num1 + num2
            elif operation == '-':
                # Ensure positive result
                if num1 < num2:
                    num1, num2 = num2, num1
                answer = num1 - num2
            else:  # multiplication
                # Use smaller numbers for multiplication
                num1 = random.randint(2, 10)
                num2 = random.randint(2, 10)
                answer = num1 * num2
            
            # Create question
            question = f"What is {num1} {operation} {num2}?"
            
            # Create encrypted answer with timestamp
            answer_data = f"{answer}:{int(time.time())}"
            encrypted_answer = hashlib.sha256(answer_data.encode()).hexdigest()
            
            logger.info(f"Generated CAPTCHA: {question} (answer: {answer})")
            
            return {
                'question': question,
                'encrypted_answer': encrypted_answer,
                'timestamp': str(int(time.time()))
            }
            
        except Exception as e:
            logger.error(f"Error generating CAPTCHA: {e}")
            # Fallback to simple addition
            return {
                'question': "What is 2 + 2?",
                'encrypted_answer': hashlib.sha256(f"4:{int(time.time())}".encode()).hexdigest(),
                'timestamp': str(int(time.time()))
            }
    
    def verify_captcha(self, user_answer: str, encrypted_answer: str, timestamp: str) -> Tuple[bool, str]:
        """
        Verify CAPTCHA answer
        
        Args:
            user_answer: User's answer to the math problem
            encrypted_answer: Encrypted correct answer
            timestamp: When the CAPTCHA was generated
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Validate input
            if not user_answer or not encrypted_answer or not timestamp:
                return False, "Invalid CAPTCHA data"
            
            # Check if CAPTCHA has expired (5 minutes)
            captcha_time = int(timestamp)
            current_time = int(time.time())
            if current_time - captcha_time > 300:  # 5 minutes
                return False, "CAPTCHA expired. Please try again."
            
            # Try to parse user answer
            try:
                answer = int(user_answer.strip())
            except ValueError:
                return False, "Please enter a valid number"
            
            # Recreate encrypted answer and compare
            answer_data = f"{answer}:{captcha_time}"
            expected_hash = hashlib.sha256(answer_data.encode()).hexdigest()
            
            if expected_hash == encrypted_answer:
                logger.info("CAPTCHA verification successful")
                return True, ""
            else:
                logger.warning(f"CAPTCHA verification failed: incorrect answer")
                return False, "Incorrect answer. Please try again."
                
        except Exception as e:
            logger.error(f"Error verifying CAPTCHA: {e}")
            return False, "CAPTCHA verification failed. Please try again."

# Global instance
math_captcha = MathCaptcha()

def generate_session_captcha() -> Dict[str, str]:
    """
    Generate CAPTCHA and store in session for stateful verification
    
    Returns:
        Dict with question for display to user
    """
    try:
        captcha_data = math_captcha.generate_captcha()
        
        # Store encrypted data in session
        session['captcha_answer'] = captcha_data['encrypted_answer']
        session['captcha_timestamp'] = captcha_data['timestamp']
        
        return {
            'question': captcha_data['question']
        }
        
    except Exception as e:
        logger.error(f"Error generating session CAPTCHA: {e}")
        return {
            'question': "What is 2 + 2?"
        }

def verify_session_captcha(user_answer: str) -> Tuple[bool, str]:
    """
    Verify CAPTCHA answer using session data
    
    Args:
        user_answer: User's answer to the math problem
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        encrypted_answer = session.get('captcha_answer')
        timestamp = session.get('captcha_timestamp')
        
        if not encrypted_answer or not timestamp:
            return False, "No CAPTCHA found. Please refresh and try again."
        
        # Verify the CAPTCHA
        is_valid, error_msg = math_captcha.verify_captcha(user_answer, encrypted_answer, timestamp)
        
        # Clear CAPTCHA from session after verification attempt
        session.pop('captcha_answer', None)
        session.pop('captcha_timestamp', None)
        
        return is_valid, error_msg
        
    except Exception as e:
        logger.error(f"Error verifying session CAPTCHA: {e}")
        return False, "CAPTCHA verification failed. Please try again."

def clear_session_captcha():
    """Clear CAPTCHA data from session"""
    session.pop('captcha_answer', None)
    session.pop('captcha_timestamp', None)