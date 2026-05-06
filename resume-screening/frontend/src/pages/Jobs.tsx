import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Plus, Upload } from 'lucide-react';
import api, { JobData } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Jobs() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const data = await api.getJobs();
        setJobs(data.jobs || []);
      } catch (err: any) {
        setError('Failed to fetch jobs');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchJobs();
  }, []);

  const handleUploadForJob = (jobId: string) => {
    // Navigate to upload page with job_id query param
    navigate(`/upload?job_id=${jobId}`);
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Available Jobs</h1>
          <p className="text-gray-600 mt-2">Select a job to upload and match resumes</p>
        </div>
        <button
          onClick={() => navigate('/upload')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Parse New Job
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          {error}
        </div>
      )}

      {/* Empty State */}
      {jobs.length === 0 ? (
        <div className="card text-center py-12">
          <Briefcase className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">No jobs yet</h2>
          <p className="text-gray-600 mb-6">Parse your first job description to get started</p>
          <button
            onClick={() => navigate('/upload')}
            className="btn-primary mx-auto flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Parse Job
          </button>
        </div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="card">
              <p className="text-sm text-gray-600">Total Jobs</p>
              <p className="text-3xl font-bold text-gray-900">{jobs.length}</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">Open Positions</p>
              <p className="text-3xl font-bold text-gray-900">
                {jobs.filter(j => j.status === 'open').length}
              </p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">Average Requirements</p>
              <p className="text-3xl font-bold text-gray-900">
                {Math.round(jobs.reduce((sum, j) => sum + (j.required_skills?.length || 0), 0) / jobs.length)}
              </p>
            </div>
          </div>

          {/* Jobs Grid */}
          <div className="grid grid-cols-1 gap-4">
            {jobs.map(job => (
              <div key={job.job_id} className="card hover:shadow-lg transition">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Briefcase className="w-5 h-5 text-blue-600" />
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {job.job_title || 'Job Position'}
                        </h3>
                        <p className="text-sm text-gray-500 font-mono">{job.job_id}</p>
                      </div>
                      <span className={`badge ${job.status === 'open' ? 'badge-success' : 'badge-gray'}`}>
                        {job.status}
                      </span>
                    </div>

                    {/* Job Details */}
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2 text-sm text-gray-700">
                        <span className="font-medium">Experience Level:</span>
                        <span className="text-gray-600">{job.experience_level || 'N/A'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-700">
                        <span className="font-medium">Years Required:</span>
                        <span className="text-gray-600">{job.experience_years} years</span>
                      </div>

                      {/* Skills Preview */}
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-sm font-medium text-gray-700 mb-2">
                          Required Skills ({job.required_skills?.length || 0})
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {job.required_skills?.slice(0, 5).map((skill, idx) => (
                            <span key={idx} className="badge badge-info text-xs">
                              {skill}
                            </span>
                          ))}
                          {(job.required_skills?.length || 0) > 5 && (
                            <span className="badge badge-gray text-xs">
                              +{(job.required_skills?.length || 0) - 5} more
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Nice to Have Skills */}
                      {job.nice_to_have_skills && job.nice_to_have_skills.length > 0 && (
                        <div className="mt-2">
                          <p className="text-sm font-medium text-gray-700 mb-2">
                            Nice to Have ({job.nice_to_have_skills.length})
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {job.nice_to_have_skills?.slice(0, 3).map((skill, idx) => (
                              <span key={idx} className="badge badge-warning text-xs">
                                {skill}
                              </span>
                            ))}
                            {(job.nice_to_have_skills?.length || 0) > 3 && (
                              <span className="badge badge-gray text-xs">
                                +{(job.nice_to_have_skills?.length || 0) - 3} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Created Date */}
                      <p className="text-xs text-gray-500 mt-3">
                        Created: {new Date(job.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  {/* Action Button */}
                  <button
                    onClick={() => handleUploadForJob(job.job_id)}
                    className="ml-4 btn-primary flex items-center gap-2 whitespace-nowrap"
                  >
                    <Upload className="w-4 h-4" />
                    Upload Resumes
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
