import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import api from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

interface JobParserProps {
  onJobCreated: (jobId: string) => void;
}

export default function JobParser({ onJobCreated }: JobParserProps) {
  const navigate = useNavigate();
  const [jobDescription, setJobDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await api.parseJob(jobDescription);
      setResult(result);
      onJobCreated(result.job_id);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to parse job description');
    } finally {
      setLoading(false);
    }
  };

  const handleProceedToUpload = () => {
    if (result?.job_id) {
      navigate('/upload');
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">Job Description Parser</h1>
        <p className="text-gray-600 text-lg">Extract requirements from a job description to match with candidates</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form Section */}
        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Job Description
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the full job description here..."
                className="input-field h-64 font-mono text-sm"
                required
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !jobDescription.trim()}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Parsing...' : 'Parse Job Description'}
            </button>
          </form>
        </div>

        {/* Results Section */}
        <div>
          {loading ? (
            <div className="card">
              <LoadingSpinner />
            </div>
          ) : result ? (
            <div className="space-y-4">
              {/* Job Title */}
              {result.job_title && (
                <div className="card bg-blue-50 border-blue-200">
                  <h3 className="text-sm font-medium text-blue-700 mb-1">Job Title</h3>
                  <p className="text-2xl font-bold text-blue-900">{result.job_title}</p>
                </div>
              )}

              {/* Job ID */}
              <div className="card">
                <h3 className="text-sm font-medium text-gray-500 mb-1">Job ID</h3>
                <p className="font-mono text-lg font-bold text-gray-900">{result.job_id}</p>
              </div>

              {/* Experience Level */}
              <div className="card">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Experience Level</h3>
                <p className="text-lg font-semibold text-gray-900">{result.experience_level}</p>
                <p className="text-sm text-gray-600">{result.experience_years}+ years required</p>
              </div>

              {/* Required Skills */}
              <div className="card">
                <h3 className="text-sm font-medium text-gray-500 mb-3">Required Skills</h3>
                <div className="flex flex-wrap gap-2">
                  {result.required_skills?.map((skill: any, idx: number) => (
                    <span key={idx} className="badge badge-success">
                      {typeof skill === 'string' ? skill : skill.skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Nice to Have Skills */}
              {result.nice_to_have_skills?.length > 0 && (
                <div className="card">
                  <h3 className="text-sm font-medium text-gray-500 mb-3">Nice to Have</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.nice_to_have_skills.map((skill: any, idx: number) => (
                      <span key={idx} className="badge badge-info">
                        {typeof skill === 'string' ? skill : skill.skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Proceed Button */}
              <button
                onClick={handleProceedToUpload}
                className="btn-success w-full flex items-center justify-center gap-2"
              >
                Proceed to Upload Resumes
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="card text-center text-gray-500">
              <p>Parsed job details will appear here</p>
            </div>
          )}
        </div>
      </div>

      {/* Example Section */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">Example Job Description</h3>
        <details className="text-blue-800">
          <summary className="cursor-pointer hover:text-blue-600 font-medium mb-2">
            Click to expand sample
          </summary>
          <pre className="mt-3 bg-white p-4 rounded border border-blue-200 overflow-auto text-sm">
{`Senior Python Backend Engineer

Requirements:
- 5+ years of Python development experience (required)
- AWS services experience including Lambda, DynamoDB, S3 (required)
- FastAPI or similar framework experience (preferred)
- Docker & Kubernetes knowledge (nice to have)
- PostgreSQL or similar database experience (required)

Responsibilities:
- Lead backend architecture decisions
- Mentor junior developers
- Design scalable systems
- Implement CI/CD pipelines`}
          </pre>
        </details>
      </div>
    </div>
  );
}
