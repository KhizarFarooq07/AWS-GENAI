import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ArrowLeft, Download } from 'lucide-react';
import api, { ResultsResponse, BatchStatusResponse } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Results() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<number>(0);
  const [downloadingUrl, setDownloadingUrl] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Polling effect for batch status
  useEffect(() => {
    let pollInterval: any = null;

    const fetchBatchStatus = async () => {
      try {
        if (!batchId) throw new Error('Batch ID not provided');
        const status = await api.getBatchStatus(batchId);
        setBatchStatus(status);

        // If still processing, continue polling
        if (status.status === 'processing' || status.status === 'pending') {
          setIsProcessing(true);
          // Fetch partial results while processing
          fetchResults();
        } else if (status.status === 'completed') {
          setIsProcessing(false);
          // Fetch final results when processing is complete
          fetchResults();
          // STOP POLLING when completed
          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
        }
      } catch (err: any) {
        console.error('Failed to fetch batch status:', err);
      }
    };

    const fetchResults = async () => {
      try {
        if (!batchId) throw new Error('Batch ID not provided');
        const data = await api.getResults(batchId);
        setResults(data);
        setLoading(false);
      } catch (err: any) {
        setError(err.response?.data?.message || 'Failed to fetch results');
        setLoading(false);
      }
    };

    // Initial fetch
    fetchBatchStatus();

    // Set up polling every 2 seconds while processing
    pollInterval = setInterval(fetchBatchStatus, 2000);

    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [batchId]);

  const handleDownload = async (filename: string) => {
    try {
      if (!batchId) return;
      setDownloadingUrl(filename);
      const { download_url } = await api.getDownloadUrl(batchId, filename);
      
      // Open presigned URL in new tab (S3 will trigger download)
      window.open(download_url, '_blank');
    } catch (err: any) {
      console.error('Failed to get download URL:', err);
      alert('Failed to generate download link. Please try again.');
    } finally {
      setDownloadingUrl(null);
    }
  };

  // Processing state - show progress
  if (isProcessing && batchStatus) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 hover:bg-gray-100 rounded-lg transition"
              >
                <ArrowLeft className="w-6 h-6" />
              </button>
              <div>
                <h1 className="text-4xl font-bold text-gray-900">Processing Resumes</h1>
                <p className="text-sm text-gray-500 font-mono mt-1">Batch: {batchId}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Progress Section */}
        <div className="space-y-6">
          {/* Status Card */}
          <div className="card">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Status</p>
                <p className="text-lg font-semibold text-blue-600 capitalize">
                  {batchStatus.status}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Progress</p>
                <p className="text-lg font-semibold text-gray-900">
                  {batchStatus.processed_files} / {batchStatus.total_files}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Completion</p>
                <p className="text-lg font-semibold text-purple-600">
                  {Math.round(batchStatus.completion_percentage)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Errors</p>
                <p className={`text-lg font-semibold ${batchStatus.failed_files > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {batchStatus.failed_files}
                </p>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="card">
            <p className="text-sm font-medium text-gray-700 mb-2">Overall Progress</p>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                style={{ width: `${batchStatus.completion_percentage}%` }}
              ></div>
            </div>
            <p className="text-right text-xs text-gray-600 mt-2">
              {Math.round(batchStatus.completion_percentage)}%
            </p>
          </div>

          {/* Resume Processing Status */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Resume Processing</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Completed:</span>
                <span className="font-semibold text-green-600">{batchStatus.processed_files}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Failed:</span>
                <span className={`font-semibold ${batchStatus.failed_files > 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {batchStatus.failed_files}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Remaining:</span>
                <span className="font-semibold text-yellow-600">
                  {batchStatus.total_files - batchStatus.processed_files - batchStatus.failed_files}
                </span>
              </div>
            </div>
          </div>

          {/* Error Log */}
          {batchStatus.errors && batchStatus.errors.length > 0 && (
            <div className="card bg-red-50 border border-red-200">
              <h3 className="text-sm font-medium text-red-700 mb-2">Errors</h3>
              <div className="space-y-1 text-xs max-h-40 overflow-auto">
                {batchStatus.errors.map((err: any, idx: number) => (
                  <div key={idx} className="text-red-600 border-b border-red-200 pb-2 last:border-b-0">
                    <p className="font-semibold">{err.filename || err.candidate_id}</p>
                    <p className="font-mono text-red-700">{err.error_message}</p>
                    {err.timestamp && <p className="text-gray-500 text-xs">{new Date(err.timestamp).toLocaleTimeString()}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Partial Results While Processing */}
          {results && results.candidates && results.candidates.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Results So Far</h3>
              <div className="space-y-2">
                {results.candidates.map((candidate, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-50 p-3 rounded">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{candidate.filename}</p>
                      <p className="text-xs text-gray-500">{candidate.status || 'processed'}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-semibold text-blue-600">{Math.round(candidate.match_percentage)}%</p>
                      <p className="text-xs text-gray-600 capitalize">{candidate.status || 'match'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Loading Animation */}
          <div className="card text-center">
            <LoadingSpinner />
            <p className="text-gray-600 mt-4">Processing your resumes...</p>
            <p className="text-sm text-gray-500 mt-2">This page will update automatically every 2 seconds</p>
          </div>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
          {error}
        </div>
        <button onClick={() => navigate('/')} className="btn-secondary mt-4">
          Back to Home
        </button>
      </div>
    );
  }

  if (!results) return null;

  const candidate = results.candidates[selectedCandidate];
  const chartData = [
    { name: 'Strong Match', value: results.summary.strong_matches, fill: '#10b981' },
    { name: 'Partial Match', value: results.summary.partial_matches, fill: '#f59e0b' },
    { name: 'Not Qualified', value: results.summary.not_qualified, fill: '#ef4444' },
  ].filter(item => item.value > 0);

  const scoreData = results.candidates.map((c) => ({
    name: `${c.filename.replace('.pdf', '').substring(0, 15)}...`,
    score: c.match_percentage,
  }));

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-gray-100 rounded-lg transition"
            >
              <ArrowLeft className="w-6 h-6" />
            </button>
            <div>
              <h1 className="text-4xl font-bold text-gray-900">Results Dashboard</h1>
              <p className="text-sm text-gray-500 font-mono mt-1">Batch: {batchId}</p>
            </div>
          </div>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Download className="w-4 h-4" />
          Export Results
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <div className="card">
          <p className="text-sm text-gray-600 mb-1">Total Candidates</p>
          <p className="text-3xl font-bold text-gray-900">{results.summary.total_candidates}</p>
        </div>
        <div className="card bg-green-50 border-green-200">
          <p className="text-sm text-green-700 mb-1">Strong Matches</p>
          <p className="text-3xl font-bold text-green-600">{results.summary.strong_matches}</p>
        </div>
        <div className="card bg-yellow-50 border-yellow-200">
          <p className="text-sm text-yellow-700 mb-1">Partial Matches</p>
          <p className="text-3xl font-bold text-yellow-600">{results.summary.partial_matches}</p>
        </div>
        <div className="card bg-red-50 border-red-200">
          <p className="text-sm text-red-700 mb-1">Not Qualified</p>
          <p className="text-3xl font-bold text-red-600">{results.summary.not_qualified}</p>
        </div>
        <div className="card bg-purple-50 border-purple-200">
          <p className="text-sm text-purple-700 mb-1">Avg Match</p>
          <p className="text-3xl font-bold text-purple-600">{results.summary.avg_match_percentage}%</p>
        </div>
      </div>

      {/* Charts and Candidates */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        {/* Status Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Status Distribution</h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-8">No data available</p>
          )}
        </div>

        {/* Match Scores */}
        <div className="card lg:col-span-2">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Match Scores</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="score" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Candidates List and Details */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Candidates List */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Candidates</h3>
          <div className="space-y-2 max-h-96 overflow-auto">
            {results.candidates.map((c, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedCandidate(idx)}
                className={`w-full text-left p-3 rounded-lg transition ${
                  selectedCandidate === idx
                    ? 'bg-blue-50 border border-blue-300'
                    : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                <p className="font-medium text-gray-900 text-sm truncate">
                  {c.filename}
                </p>
                <div className="flex items-center justify-between mt-1">
                  <span className={`badge text-xs ${
                    c.status === 'strong_match' ? 'badge-success' :
                    c.status === 'partial_match' ? 'badge-warning' :
                    'badge-danger'
                  }`}>
                    {c.status}
                  </span>
                  <span className="text-sm font-bold text-gray-900">
                    {c.match_percentage}%
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Candidate Details */}
        {candidate && (
          <div className="lg:col-span-3 space-y-6">
            {/* Header */}
            <div className="card">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{candidate.filename}</h2>
                  <span className={`badge text-lg mt-2 py-1.5 px-3 ${
                    candidate.status === 'strong_match' ? 'badge-success' :
                    candidate.status === 'partial_match' ? 'badge-warning' :
                    'badge-danger'
                  }`}>
                    {candidate.status.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>
                <button
                  onClick={() => handleDownload(candidate.filename)}
                  disabled={downloadingUrl === candidate.filename}
                  className="btn-outline flex items-center gap-2 disabled:opacity-50"
                >
                  <Download className="w-4 h-4" />
                  {downloadingUrl === candidate.filename ? 'Downloading...' : 'Download'}
                </button>
              </div>
            </div>

            {/* Score */}
            <div className="card">
              <p className="text-sm text-gray-600 mb-2">Overall Match Score</p>
              <div className="flex items-end gap-4">
                <div>
                  <p className="text-5xl font-bold text-blue-600">
                    {candidate.match_percentage}%
                  </p>
                </div>
                <div className="flex-1">
                  <div className="bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${candidate.match_percentage}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Experience */}
            <div className="grid grid-cols-2 gap-4">
              <div className="card">
                <p className="text-sm text-gray-600 mb-1">Experience Level</p>
                <p className="text-xl font-semibold text-gray-900">
                  {candidate.experience_level || 'N/A'}
                </p>
              </div>
              <div className="card">
                <p className="text-sm text-gray-600 mb-1">Job Titles</p>
                <p className="text-sm font-semibold text-gray-900">
                  {candidate.job_titles?.join(', ') || 'N/A'}
                </p>
              </div>
            </div>

            {/* Matched Skills */}
            {candidate.matched_skills.length > 0 && (
              <div className="card">
                <h3 className="text-sm font-medium text-green-700 mb-3">
                  ✓ Matched Skills ({candidate.matched_skills.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {candidate.matched_skills.map((skill, idx) => (
                    <span key={idx} className="badge badge-success">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Missing Skills */}
            {candidate.missing_skills.length > 0 && (
              <div className="card">
                <h3 className="text-sm font-medium text-red-700 mb-3">
                  ✗ Missing Skills ({candidate.missing_skills.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {candidate.missing_skills.map((skill, idx) => (
                    <span key={idx} className="badge badge-danger">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Bonus Skills */}
            {candidate.bonus_skills.length > 0 && (
              <div className="card">
                <h3 className="text-sm font-medium text-blue-700 mb-3">
                  ★ Bonus Skills ({candidate.bonus_skills.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {candidate.bonus_skills.map((skill, idx) => (
                    <span key={idx} className="badge badge-info">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* AI Candidate Assessment (Bedrock) */}
            {candidate.bedrock_fit_score !== undefined && (
              <div className="card border-2 border-purple-200 bg-purple-50">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-purple-900">🤖 AI Candidate Assessment</h3>
                  <span className={`badge text-sm py-1 px-3 ${
                    candidate.bedrock_recommendation === 'INTERVIEW' ? 'badge-success' :
                    candidate.bedrock_recommendation === 'PASS' ? 'badge-danger' :
                    'badge-warning'
                  }`}>
                    {candidate.bedrock_recommendation === 'INTERVIEW' ? '✓ INTERVIEW' :
                     candidate.bedrock_recommendation === 'PASS' ? '✗ PASS' :
                     '? MAYBE'}
                  </span>
                </div>

                {/* Bedrock Fit Score */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-purple-700">AI Fit Score</p>
                    <span className="text-2xl font-bold text-purple-600">{candidate.bedrock_fit_score}/100</span>
                  </div>
                  <div className="bg-purple-200 rounded-full h-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full"
                      style={{ width: `${candidate.bedrock_fit_score}%` }}
                    ></div>
                  </div>
                </div>

                {/* Reasoning */}
                {candidate.bedrock_reasoning && (
                  <div className="mb-4 p-3 bg-white rounded-lg border border-purple-200">
                    <p className="text-sm text-gray-600 mb-2">Analysis</p>
                    <p className="text-sm text-gray-900 leading-relaxed">{candidate.bedrock_reasoning}</p>
                  </div>
                )}

                {/* Strengths */}
                {candidate.bedrock_strengths && candidate.bedrock_strengths.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-medium text-green-700 mb-2">✓ Strengths</p>
                    <ul className="text-xs text-gray-700 space-y-1">
                      {candidate.bedrock_strengths.map((strength: string, idx: number) => (
                        <li key={idx} className="flex gap-2">
                          <span className="text-green-600 mt-0.5">•</span>
                          <span>{strength}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Gaps */}
                {candidate.bedrock_gaps && candidate.bedrock_gaps.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-700 mb-2">✗ Areas for Growth</p>
                    <ul className="text-xs text-gray-700 space-y-1">
                      {candidate.bedrock_gaps.map((gap: string, idx: number) => (
                        <li key={idx} className="flex gap-2">
                          <span className="text-red-600 mt-0.5">•</span>
                          <span>{gap}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
