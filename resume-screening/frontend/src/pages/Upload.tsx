import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Upload as UploadIcon, CheckCircle, AlertCircle } from 'lucide-react';
import api, { JobData } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

interface UploadProps {
  jobId: string | null;
}

export default function Upload({ jobId: propJobId }: UploadProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [showJobSelector, setShowJobSelector] = useState(false);

  // Get job_id from URL params or props
  useEffect(() => {
    const queryJobId = searchParams.get('job_id');
    const initialJobId = queryJobId || propJobId;
    if (initialJobId) {
      setSelectedJobId(initialJobId);
    }
  }, [searchParams, propJobId]);

  // Load available jobs
  useEffect(() => {
    const fetchJobs = async () => {
      setLoadingJobs(true);
      try {
        const data = await api.getJobs();
        setJobs(data.jobs || []);
      } catch (err) {
        console.error('Failed to fetch jobs:', err);
      } finally {
        setLoadingJobs(false);
      }
    };
    fetchJobs();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        file => file.type === 'application/pdf'
      );
      if (selectedFiles.length !== e.target.files.length) {
        setError('Only PDF files are allowed');
      }
      setFiles(selectedFiles);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.type === 'application/pdf'
    );
    setFiles(droppedFiles);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId) {
      setError('Please select or parse a job description');
      return;
    }

    if (files.length === 0) {
      setError('Please select at least one PDF file');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.uploadResumes(files, selectedJobId);
      // HTTP 202 Accepted - processing started
      // Redirect to Results page for polling
      if (result.batch_id) {
        setTimeout(() => {
          navigate(`/results/${result.batch_id}`);
        }, 500);
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to upload resumes');
      setLoading(false);
    }
  };

  const selectedJob = jobs.find(j => j.job_id === selectedJobId);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">Upload Resumes</h1>
        <p className="text-gray-600 text-lg">Upload candidate PDFs to extract skills and match with job requirements</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Upload Section */}
        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Job Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select or Parse Job
              </label>
              {selectedJob ? (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-2">
                  <p className="text-sm font-medium text-gray-900">{selectedJob.job_title || 'Job Position'}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {selectedJob.job_id}
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    {selectedJob.required_skills?.length} required skills
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowJobSelector(!showJobSelector)}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2"
                  >
                    Change Job
                  </button>
                </div>
              ) : (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-2">
                  <p className="text-sm text-yellow-800">
                    {jobs.length === 0 ? 'No saved jobs found' : 'Select a job from the list below'}
                  </p>
                </div>
              )}

              {/* Job Dropdown */}
              {(showJobSelector || !selectedJobId) && (
                <div className="space-y-2 mb-4 border border-gray-300 rounded-lg p-3 bg-gray-50 max-h-48 overflow-auto">
                  {loadingJobs ? (
                    <p className="text-sm text-gray-600">Loading jobs...</p>
                  ) : jobs.length === 0 ? (
                    <p className="text-sm text-gray-600">No jobs available</p>
                  ) : (
                    jobs.map(job => (
                      <button
                        key={job.job_id}
                        type="button"
                        onClick={() => {
                          setSelectedJobId(job.job_id);
                          setShowJobSelector(false);
                        }}
                        className="w-full text-left p-2 rounded hover:bg-blue-100 transition text-sm"
                      >
                        <p className="font-medium text-gray-900">{job.job_title || 'Job Position'}</p>
                        <p className="text-xs text-gray-500">
                          {job.job_id}
                        </p>
                        <p className="text-xs text-gray-600 mt-1">
                          {job.experience_level} • {job.required_skills?.length} skills
                        </p>
                      </button>
                    ))
                  )}
                  <button
                    type="button"
                    onClick={() => navigate('/')}
                    className="w-full text-left p-2 rounded bg-blue-100 hover:bg-blue-200 transition text-sm font-medium text-blue-700 mt-2"
                  >
                    + Parse New Job
                  </button>
                </div>
              )}
            </div>

            {/* Drag and Drop */}
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition"
            >
              <UploadIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-700 font-medium mb-1">
                Drag and drop PDFs here or click to select
              </p>
              <p className="text-sm text-gray-500 mb-4">Maximum 10 files, 50MB each</p>
              <input
                type="file"
                multiple
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
                id="file-input"
                disabled={loading}
              />
              <label
                htmlFor="file-input"
                className="btn-outline inline-block cursor-pointer"
              >
                Select Files
              </label>
            </div>

            {/* Selected Files */}
            {files.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700 mb-3">
                  Selected Files ({files.length})
                </p>
                <ul className="space-y-2">
                  {files.map((file, idx) => (
                    <li key={idx} className="flex items-center text-sm text-gray-600">
                      <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                      {file.name}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex gap-3 text-red-700">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                {error}
              </div>
            )}

            {!selectedJobId && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex gap-3 text-yellow-700">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                Please select or parse a job description
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !selectedJobId || files.length === 0}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Uploading...' : 'Upload and Process'}
            </button>
          </form>
        </div>

        {/* Results Section */}
        <div>
          {loading ? (
            <div className="card">
              <div className="text-center">
                <LoadingSpinner />
                <p className="text-gray-600 mt-4">Uploading resumes...</p>
                <p className="text-sm text-gray-500 mt-2">You'll be redirected to the progress page shortly</p>
              </div>
            </div>
          ) : (
            <div className="card text-center text-gray-500">
              <p>Upload resumes to start processing</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
