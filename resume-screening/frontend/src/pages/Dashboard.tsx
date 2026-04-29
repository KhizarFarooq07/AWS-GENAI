import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ArrowRight, TrendingUp, Users, Target, Calendar } from 'lucide-react';
import api, { BatchSummary } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Dashboard() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterJobId, setFilterJobId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'date' | 'match'>('date');

  useEffect(() => {
    const fetchBatches = async () => {
      try {
        const data = await api.getBatches();
        setBatches(data.batches || []);
      } catch (err: any) {
        setError('Failed to fetch batches');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchBatches();
  }, []);

  const filteredBatches = filterJobId
    ? batches.filter(b => b.job_id === filterJobId)
    : batches;

  const sortedBatches = [...filteredBatches].sort((a, b) => {
    if (sortBy === 'date') {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    } else {
      return b.avg_match_percentage - a.avg_match_percentage;
    }
  });

  // Calculate dashboard stats
  const totalBatches = batches.length;
  const totalCandidates = batches.reduce((sum, b) => sum + b.total_candidates, 0);
  const totalStrongMatches = batches.reduce((sum, b) => sum + b.strong_matches, 0);
  const avgMatchOverall = totalBatches > 0
    ? (batches.reduce((sum, b) => sum + b.avg_match_percentage, 0) / totalBatches).toFixed(2)
    : 0;

  // Unique jobs
  const uniqueJobs = new Set(batches.map(b => b.job_id)).size;

  // Chart data: status distribution across all batches
  const statusData = [
    { name: 'Strong Match', value: totalStrongMatches, fill: '#10b981' },
    { name: 'Partial Match', value: batches.reduce((sum, b) => sum + b.partial_matches, 0), fill: '#f59e0b' },
    { name: 'Not Qualified', value: batches.reduce((sum, b) => sum + b.not_qualified, 0), fill: '#ef4444' },
  ].filter(item => item.value > 0);

  // Recent batches for line chart
  const recentBatches = sortedBatches.slice(0, 10).map(b => ({
    name: `${b.batch_id.substring(0, 8)}...`,
    avg_match: b.avg_match_percentage,
    candidates: b.total_candidates,
  }));

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">Dashboard</h1>
        <p className="text-gray-600">Overview of all batches and recruitment campaigns</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Batches</p>
              <p className="text-3xl font-bold text-gray-900">{totalBatches}</p>
            </div>
            <Calendar className="w-8 h-8 text-blue-500 opacity-20" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Candidates</p>
              <p className="text-3xl font-bold text-gray-900">{totalCandidates}</p>
            </div>
            <Users className="w-8 h-8 text-purple-500 opacity-20" />
          </div>
        </div>

        <div className="card bg-green-50 border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-700">Strong Matches</p>
              <p className="text-3xl font-bold text-green-600">{totalStrongMatches}</p>
            </div>
            <Target className="w-8 h-8 text-green-500 opacity-20" />
          </div>
        </div>

        <div className="card bg-blue-50 border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-700">Unique Jobs</p>
              <p className="text-3xl font-bold text-blue-600">{uniqueJobs}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-blue-500 opacity-20" />
          </div>
        </div>

        <div className="card bg-purple-50 border-purple-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-purple-700">Avg Match %</p>
              <p className="text-3xl font-bold text-purple-600">{avgMatchOverall}%</p>
            </div>
            <TrendingUp className="w-8 h-8 text-purple-500 opacity-20" />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Overall Status Distribution</h3>
          {statusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-16">No data available</p>
          )}
        </div>

        {/* Recent Batch Performance */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Batch Performance</h3>
          {recentBatches.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={recentBatches}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="avg_match" fill="#3b82f6" name="Avg Match %" />
                <Bar dataKey="candidates" fill="#8b5cf6" name="Candidates" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-16">No data available</p>
          )}
        </div>
      </div>

      {/* Filters and Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">All Batches</h3>
          <div className="flex gap-4">
            {/* Sort */}
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as 'date' | 'match')}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="date">Sort: Newest First</option>
              <option value="match">Sort: Highest Match</option>
            </select>

            {/* Filter */}
            {filterJobId && (
              <button
                onClick={() => setFilterJobId(null)}
                className="btn-outline text-sm"
              >
                Clear Filter
              </button>
            )}
          </div>
        </div>

        {/* Batches Table */}
        <div className="card overflow-x-auto">
          {sortedBatches.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500">No batches found</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-700">Batch ID</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-700">Job Title</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-700">Job ID</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Candidates</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Strong</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Partial</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Not Qualified</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Avg Match</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-700">Created</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-700">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedBatches.map(batch => (
                  <tr key={batch.batch_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4 text-sm font-mono text-gray-600">
                      {batch.batch_id.substring(0, 12)}...
                    </td>
                    <td className="py-3 px-4 text-sm font-medium text-gray-900">
                      {batch.job_title || 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <button
                        onClick={() => setFilterJobId(batch.job_id)}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        {batch.job_id}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-sm text-center font-semibold text-gray-900">
                      {batch.total_candidates}
                    </td>
                    <td className="py-3 px-4 text-sm text-center">
                      <span className="badge badge-success">{batch.strong_matches}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-center">
                      <span className="badge badge-warning">{batch.partial_matches}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-center">
                      <span className="badge badge-danger">{batch.not_qualified}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-16 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${batch.avg_match_percentage}%` }}
                          ></div>
                        </div>
                        <span className="font-semibold text-gray-900 text-sm w-8">
                          {batch.avg_match_percentage}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {new Date(batch.created_at).toLocaleDateString()} {new Date(batch.created_at).toLocaleTimeString()}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => navigate(`/results/${batch.batch_id}`)}
                        className="btn-primary flex items-center gap-2 text-sm"
                      >
                        View <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
