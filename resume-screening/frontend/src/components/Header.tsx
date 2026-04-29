import { Link } from 'react-router-dom';
import { Briefcase } from 'lucide-react';

export default function Header() {
  return (
    <header className="bg-white shadow">
      <nav className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-2xl font-bold text-blue-600">
          <Briefcase className="w-8 h-8" />
          ResumeMatch
        </Link>
        <div className="flex gap-6">
          <Link to="/dashboard" className="text-gray-700 hover:text-blue-600 font-medium">
            Dashboard
          </Link>
          <Link to="/jobs" className="text-gray-700 hover:text-blue-600 font-medium">
            Available Jobs
          </Link>
          <Link to="/" className="text-gray-700 hover:text-blue-600 font-medium">
            Parse Job
          </Link>
          <Link to="/upload" className="text-gray-700 hover:text-blue-600 font-medium">
            Upload Resumes
          </Link>
        </div>
      </nav>
    </header>
  );
}
