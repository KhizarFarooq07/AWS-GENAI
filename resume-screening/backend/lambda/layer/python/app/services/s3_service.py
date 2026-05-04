"""
S3 Service for Resume Storage and Retrieval
Handles uploading resumes to AWS S3, generating presigned URLs, and managing file lifecycle
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os
import logging

# Try to load .env file if it exists (for local dev)
# In Lambda, this will be skipped and environment variables will be used directly
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available (Lambda environment)

logger = logging.getLogger(__name__)


class S3Service:
    """Manages resume storage and retrieval from AWS S3"""

    def __init__(self):
        """Initialize S3 client with adaptive retry strategy"""
        config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'  # Auto-adjusts backoff based on load
            }
        )

        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            config=config
        )

        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'resume-screening-bucket')
        # Skip bucket check in Lambda (will fail due to permissions/credentials)
        # Bucket operations will still work if permissions are correct
        if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
            logger.info(f"ℹ️  Running in Lambda, skipping bucket verification")
        else:
            self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Verify bucket exists, create if it doesn't"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3 bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.info(f"🔄 Creating S3 bucket '{self.bucket_name}'...")
                try:
                    region = os.getenv('AWS_REGION', 'us-east-1')
                    if region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    logger.info(f"✅ Created S3 bucket '{self.bucket_name}'")
                except Exception as create_err:
                    logger.error(f"❌ Failed to create bucket: {str(create_err)}")
                    raise
            else:
                logger.error(f"❌ Error accessing bucket: {str(e)}")
                raise

    def upload_file(self, file_path, batch_id, filename):
        """
        Upload a resume PDF to S3
        
        Args:
            file_path (str): Local path to the file
            batch_id (str): Batch ID for organization
            filename (str): Original filename
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                's3_key': 's3 object key',
                's3_url': 's3 file URL',
                'size': file size in bytes,
                'error': error message if failed
            }
        """
        try:
            # Create S3 key with batch organization
            s3_key = f"resumes/{batch_id}/{filename}"

            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'application/pdf'}
            )

            file_size = os.path.getsize(file_path)
            s3_url = f"s3://{self.bucket_name}/{s3_key}"

            logger.info(f"✅ Uploaded {filename} to S3: {s3_url} ({file_size} bytes)")

            return {
                'status': 'success',
                's3_key': s3_key,
                's3_url': s3_url,
                'size': file_size
            }

        except ClientError as e:
            error_msg = f"S3 upload failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error uploading to S3: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def get_presigned_url(self, s3_key, expiration=3600):
        """
        Generate a presigned URL for temporary file access
        
        Args:
            s3_key (str): S3 object key
            expiration (int): URL expiration time in seconds (default: 1 hour)
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'url': presigned URL,
                'error': error message if failed
            }
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )

            logger.info(f"✅ Generated presigned URL for {s3_key} (expires in {expiration}s)")

            return {
                'status': 'success',
                'url': url
            }

        except ClientError as e:
            error_msg = f"Failed to generate presigned URL: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def download_file(self, s3_key, local_path):
        """
        Download a file from S3 to local storage
        
        Args:
            s3_key (str): S3 object key
            local_path (str): Local destination path
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'local_path': local path,
                'size': file size,
                'error': error message if failed
            }
        """
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            file_size = os.path.getsize(local_path)

            logger.info(f"✅ Downloaded {s3_key} from S3 ({file_size} bytes)")

            return {
                'status': 'success',
                'local_path': local_path,
                'size': file_size
            }

        except ClientError as e:
            error_msg = f"S3 download failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def delete_file(self, s3_key):
        """
        Delete a file from S3
        
        Args:
            s3_key (str): S3 object key
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'error': error message if failed
            }
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)

            logger.info(f"✅ Deleted {s3_key} from S3")

            return {'status': 'success'}

        except ClientError as e:
            error_msg = f"S3 delete failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def list_batch_files(self, batch_id):
        """
        List all files for a given batch
        
        Args:
            batch_id (str): Batch ID
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'files': list of file info,
                'count': number of files,
                'error': error message if failed
            }
        """
        try:
            prefix = f"resumes/{batch_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        's3_key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'storage_class': obj['StorageClass']
                    })

            logger.info(f"✅ Listed {len(files)} files for batch {batch_id}")

            return {
                'status': 'success',
                'files': files,
                'count': len(files)
            }

        except ClientError as e:
            error_msg = f"S3 list failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
                'count': 0,
                'files': []
            }

    def get_file_info(self, s3_key):
        """
        Get metadata for a specific file
        
        Args:
            s3_key (str): S3 object key
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'size': file size,
                'last_modified': last modified timestamp,
                'etag': file etag,
                'error': error message if failed
            }
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )

            logger.info(f"✅ Retrieved metadata for {s3_key}")

            return {
                'status': 'success',
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'etag': response['ETag'],
                'content_type': response.get('ContentType', 'unknown')
            }

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                error_msg = "File not found in S3"
            else:
                error_msg = f"S3 head object failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg
            }

    def delete_batch_files(self, batch_id):
        """
        Delete all files for a given batch
        
        Args:
            batch_id (str): Batch ID
            
        Returns:
            dict: {
                'status': 'success' | 'error',
                'deleted_count': number of deleted files,
                'error': error message if failed
            }
        """
        try:
            prefix = f"resumes/{batch_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            deleted_count = 0
            if 'Contents' in response:
                for obj in response['Contents']:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=obj['Key'])
                    deleted_count += 1

            logger.info(f"✅ Deleted {deleted_count} files for batch {batch_id}")

            return {
                'status': 'success',
                'deleted_count': deleted_count
            }

        except ClientError as e:
            error_msg = f"S3 batch delete failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
                'deleted_count': 0
            }
