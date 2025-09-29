"""
Simple math-based CAPTCHA system for preventing automated abuse
"""
import hashlib
import logging
import os
import random
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple

from flask import session
from db_base import db

logger = logging.getLogger(__name__)

class MathCaptcha:
    """Simple math-based CAPTCHA for authentication endpoints"""
    
    def __init__(self):
        self.operations = ['+', '-', '*']
        self.max_number = 20  # Keep numbers manageable for users
        
    def generate_captcha(self) -> dict[str, str]:
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
    
    def verify_captcha(self, user_answer: str, encrypted_answer: str, timestamp: str) -> tuple[bool, str]:
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
                logger.warning("CAPTCHA verification failed: incorrect answer")
                return False, "Incorrect answer. Please try again."
                
        except Exception as e:
            logger.error(f"Error verifying CAPTCHA: {e}")
            return False, "CAPTCHA verification failed. Please try again."

# Global instance
math_captcha = MathCaptcha()

def generate_session_captcha() -> dict[str, str]:
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

def verify_session_captcha(user_answer: str) -> tuple[bool, str]:
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

# Nonce-based CAPTCHA system (session-independent)
def generate_nonce_captcha() -> dict[str, str]:
    """
    Generate CAPTCHA and store in database using nonce for stateless verification
    
    Returns:
        Dict with question and nonce for form submission
    """
    try:
        # Check for dev bypass
        if os.getenv("CAPTCHA_BYPASS") == "1":
            logger.info("CAPTCHA bypass enabled - skipping generation")
            return {
                'question': "CAPTCHA bypassed for development",
                'nonce': "dev_bypass_nonce"
            }
        
        captcha_data = math_captcha.generate_captcha()
        nonce = secrets.token_urlsafe(16)
        
        # Store in database with 2-minute TTL
        expires_at = datetime.utcnow() + timedelta(minutes=2)
        
        # Clean up old expired entries first
        db.session.execute(db.text(
            "DELETE FROM captcha_nonces WHERE expires_at < now()"
        ))
        
        # Insert new CAPTCHA nonce
        db.session.execute(db.text(
            "INSERT INTO captcha_nonces (nonce, answer, expires_at) VALUES (:nonce, :answer, :expires_at)"
        ), {
            'nonce': nonce,
            'answer': str(captcha_data['timestamp'] + ':' + captcha_data['encrypted_answer']),
            'expires_at': expires_at
        })
        db.session.commit()
        
        logger.info(f"Generated nonce CAPTCHA: {captcha_data['question']} (nonce: {nonce[:8]}...)")
        
        return {
            'question': captcha_data['question'],
            'nonce': nonce
        }
        
    except Exception as e:
        logger.error(f"Error generating nonce CAPTCHA: {e}")
        db.session.rollback()
        # Fallback
        return {
            'question': "What is 2 + 2?",
            'nonce': "fallback_nonce"
        }

def verify_nonce_captcha(nonce: str, user_answer: str) -> tuple[bool, str]:
    """
    Verify CAPTCHA answer using nonce-based storage
    
    Args:
        nonce: CAPTCHA nonce from form
        user_answer: User's answer to the math problem
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check for dev bypass
        if os.getenv("CAPTCHA_BYPASS") == "1":
            logger.info("CAPTCHA bypass enabled - verification skipped")
            return True, ""
        
        # Handle fallback nonce
        if nonce == "fallback_nonce":
            return user_answer.strip() == "4", "Incorrect answer" if user_answer.strip() != "4" else ""
        
        if not nonce or not user_answer:
            return False, "CAPTCHA nonce or answer missing"
            
        # Fetch from database
        result = db.session.execute(db.text(
            "SELECT answer, expires_at FROM captcha_nonces WHERE nonce = :nonce"
        ), {'nonce': nonce}).fetchone()
        
        if not result:
            return False, "CAPTCHA not found or expired"
            
        answer_data, expires_at = result
        
        # Check expiration
        if datetime.utcnow() > expires_at:
            # Clean up expired entry
            db.session.execute(db.text(
                "DELETE FROM captcha_nonces WHERE nonce = :nonce"
            ), {'nonce': nonce})
            db.session.commit()
            return False, "CAPTCHA expired. Please try again."
        
        # Parse stored answer data (timestamp:encrypted_answer)
        try:
            timestamp, encrypted_answer = answer_data.split(':', 1)
        except ValueError:
            logger.error(f"Invalid answer data format for nonce {nonce}")
            return False, "CAPTCHA verification failed"
        
        # Verify using existing math_captcha logic
        is_valid, error_msg = math_captcha.verify_captcha(user_answer, encrypted_answer, timestamp)
        
        # Delete nonce after verification (one-time use)
        db.session.execute(db.text(
            "DELETE FROM captcha_nonces WHERE nonce = :nonce"
        ), {'nonce': nonce})
        db.session.commit()
        
        return is_valid, error_msg
        
    except Exception as e:
        logger.error(f"Error verifying nonce CAPTCHA: {e}")
        db.session.rollback()
        return False, "CAPTCHA verification failed. Please try again."

def cleanup_expired_captcha_nonces():
    """Clean up expired CAPTCHA nonces from database"""
    try:
        result = db.session.execute(db.text(
            "DELETE FROM captcha_nonces WHERE expires_at < now() RETURNING nonce"
        ))
        count = len(result.fetchall())
        db.session.commit()
        if count > 0:
            logger.info(f"Cleaned up {count} expired CAPTCHA nonces")
    except Exception as e:
        logger.error(f"Error cleaning up expired CAPTCHA nonces: {e}")
        db.session.rollback()