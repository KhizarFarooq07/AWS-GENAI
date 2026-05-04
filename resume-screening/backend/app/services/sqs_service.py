"""
SQS Service for Asynchronous Resume Processing
Handles queuing resume processing jobs for Lambda workers
"""

import json
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class SQSService:
    """Manages AWS SQS queue for asynchronous resume processing"""

    def __init__(self):
        """Initialize SQS client with adaptive retry strategy"""
        retry_config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'  # Auto-adjusts backoff based on load
            },
            read_timeout=60
        )

        self.sqs_client = boto3.client(
            'sqs',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            config=retry_config,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )

        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.queue_name = os.getenv('SQS_QUEUE_NAME', 'resume-processing-queue')

        if not self.queue_url:
            raise ValueError("SQS_QUEUE_URL not configured in .env")

        logger.info(f"✅ SQS Service initialized with queue: {self.queue_name}")

    def send_message(self, message_body: dict) -> dict:
        """
        Send message to SQS queue for processing
        
        Args:
            message_body (dict): Message payload containing batch_id, job_id, candidate_id, etc.
        
        Returns:
            dict: {
                'status': 'success' | 'error',
                'message_id': str,
                'error': str (if status is error)
            }
        """
        try:
            logger.info(f"📤 Sending message to SQS: batch_id={message_body.get('batch_id')}, candidate={message_body.get('candidate_id')}")
            logger.debug(f"Queue URL: {self.queue_url}")
            logger.debug(f"Message body: {json.dumps(message_body)}")

            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'batch_id': {
                        'StringValue': str(message_body.get('batch_id', '')),
                        'DataType': 'String'
                    },
                    'job_id': {
                        'StringValue': str(message_body.get('job_id', '')),
                        'DataType': 'String'
                    },
                    'candidate_id': {
                        'StringValue': str(message_body.get('candidate_id', '')),
                        'DataType': 'String'
                    }
                }
            )

            message_id = response.get('MessageId')
            logger.info(f"✅ Message sent to SQS: MessageId={message_id}")

            return {
                'status': 'success',
                'message_id': message_id
            }

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg_detail = e.response.get('Error', {}).get('Message', str(e))
            error_msg = f"SQS send_message failed ({error_code}): {error_msg_detail}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Queue URL: {self.queue_url}")
            logger.error(f"   Message Body: {json.dumps(message_body)}")
            return {
                'status': 'error',
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error sending to SQS: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Queue URL: {self.queue_url}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def send_batch_messages(self, messages: list) -> dict:
        """
        Send multiple messages to SQS queue in batch
        
        Args:
            messages (list): List of message dicts
        
        Returns:
            dict: {
                'status': 'success' | 'partial' | 'error',
                'successful': int,
                'failed': int,
                'failed_messages': list
            }
        """
        try:
            logger.info(f"📤 Sending batch of {len(messages)} messages to SQS")

            entries = []
            for idx, message in enumerate(messages):
                entries.append({
                    'Id': str(idx),
                    'MessageBody': json.dumps(message),
                    'MessageAttributes': {
                        'batch_id': {
                            'StringValue': str(message.get('batch_id', '')),
                            'DataType': 'String'
                        },
                        'job_id': {
                            'StringValue': str(message.get('job_id', '')),
                            'DataType': 'String'
                        },
                        'candidate_id': {
                            'StringValue': str(message.get('candidate_id', '')),
                            'DataType': 'String'
                        }
                    }
                })

            response = self.sqs_client.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))

            logger.info(f"✅ Batch send complete: {successful} successful, {failed} failed")

            return {
                'status': 'success' if failed == 0 else 'partial' if successful > 0 else 'error',
                'successful': successful,
                'failed': failed,
                'failed_messages': response.get('Failed', [])
            }

        except ClientError as e:
            error_msg = f"SQS send_message_batch failed: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'successful': 0,
                'failed': len(messages),
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error in batch send: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'successful': 0,
                'failed': len(messages),
                'error': error_msg
            }

    def receive_messages(self, max_messages: int = 1, wait_time: int = 20) -> list:
        """
        Receive messages from SQS queue (used by Lambda)
        
        Args:
            max_messages (int): Maximum number of messages to retrieve (1-10)
            wait_time (int): Long polling wait time in seconds (0-20)
        
        Returns:
            list: List of message dicts with MessageId, Body, ReceiptHandle
        """
        try:
            max_messages = min(max_messages, 10)  # SQS max is 10
            wait_time = min(wait_time, 20)  # Max long poll is 20 seconds

            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])
            logger.info(f"📥 Received {len(messages)} message(s) from SQS")

            return messages

        except ClientError as e:
            logger.error(f"SQS receive_message failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error receiving messages: {str(e)}")
            return []

    def delete_message(self, receipt_handle: str) -> bool:
        """
        Delete message from SQS queue after successful processing
        
        Args:
            receipt_handle (str): ReceiptHandle from received message
        
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info(f"✅ Message deleted from SQS")
            return True

        except ClientError as e:
            logger.error(f"SQS delete_message failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting message: {str(e)}")
            return False

    def delete_batch_messages(self, receipt_handles: list) -> dict:
        """
        Delete multiple messages from SQS queue
        
        Args:
            receipt_handles (list): List of ReceiptHandles
        
        Returns:
            dict: {
                'status': 'success' | 'partial' | 'error',
                'successful': int,
                'failed': int
            }
        """
        try:
            if not receipt_handles:
                return {'status': 'success', 'successful': 0, 'failed': 0}

            entries = [
                {'Id': str(idx), 'ReceiptHandle': handle}
                for idx, handle in enumerate(receipt_handles)
            ]

            response = self.sqs_client.delete_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))

            logger.info(f"✅ Batch delete complete: {successful} successful, {failed} failed")

            return {
                'status': 'success' if failed == 0 else 'partial',
                'successful': successful,
                'failed': failed
            }

        except ClientError as e:
            logger.error(f"SQS delete_message_batch failed: {str(e)}")
            return {
                'status': 'error',
                'successful': 0,
                'failed': len(receipt_handles)
            }

    def get_queue_attributes(self) -> dict:
        """
        Get queue attributes (approximate message counts, etc.)
        
        Returns:
            dict: Queue attributes including:
                - ApproximateNumberOfMessages
                - ApproximateNumberOfMessagesNotVisible
                - ApproximateNumberOfMessagesDelayed
                - VisibilityTimeout
                - MessageRetentionPeriod
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['All']
            )

            attributes = response.get('Attributes', {})
            logger.info(f"📊 Queue stats: {attributes.get('ApproximateNumberOfMessages')} messages waiting")

            return {
                'status': 'success',
                'attributes': attributes
            }

        except ClientError as e:
            logger.error(f"SQS get_queue_attributes failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def purge_queue(self) -> bool:
        """
        Purge all messages from queue (use with caution!)
        
        Returns:
            bool: True if queue purged, False otherwise
        """
        try:
            logger.warning(f"⚠️  Purging SQS queue: {self.queue_name}")
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
            return True

        except ClientError as e:
            logger.error(f"SQS purge_queue failed: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """
        Test SQS connection by getting queue attributes
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            result = self.get_queue_attributes()
            is_connected = result.get('status') == 'success'
            
            if is_connected:
                logger.info("✅ SQS connection test passed")
            else:
                logger.error("❌ SQS connection test failed")
            
            return is_connected

        except Exception as e:
            logger.error(f"SQS connection test failed: {str(e)}")
            return False
