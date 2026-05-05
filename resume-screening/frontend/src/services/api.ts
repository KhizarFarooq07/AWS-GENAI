import axios, { AxiosInstance } from 'axios';

interface JobParseRequest {
  job_description: string;
}

interface JobParseResponse {
  job_id: string;
  status: string;
  job_title?: string;
  required_skills: Array<{ skill: string; confidence: number }>;
  nice_to_have_skills: Array<{ skill: string; confidence: number }>;
  experience_level: string;
  experience_years: number;
}

interface JobData {
  job_id: string;
  job_title?: string;
  job_description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  experience_level: string;
  experience_years: number;
  status: string;
  created_at: string;
}

interface AllJobsResponse {
  status: string;
  jobs: JobData[];
  total: number;
}

interface BatchSummary {
  batch_id: string;
  job_id: string;
  job_title?: string;
  created_at: string;
  total_candidates: number;
  strong_matches: number;
  partial_matches: number;
  not_qualified: number;
  avg_match_percentage: number;
}

interface AllBatchesResponse {
  status: string;
  batches: BatchSummary[];
  total: number;
}

interface UploadResponse {
  batch_id: string;
  job_id: string;
  status: string;
  files_received: number;
  files: Array<{
    filename: string;
    s3_url?: string;
    match_percentage: number;
    status: string;
    matched_skills: string[];
    missing_skills: string[];
    bonus_skills: string[];
  }>;
  extraction_summary: {
    total_files: number;
    successful_text_extractions: number;
    successful_skill_extractions: number;
    total_skills_found: number;
    successful_matches: number;
    avg_match_percentage: number;
  };
}

interface ResultsResponse {
  batch_id: string;
  status: string;
  summary: {
    total_candidates: number;
    strong_matches: number;
    partial_matches: number;
    not_qualified: number;
    avg_match_percentage: number;
  };
  candidates: Array<{
    filename: string;
    match_percentage: number;
    status: string;
    matched_skills: string[];
    missing_skills: string[];
    bonus_skills: string[];
    experience_level: string;
    job_titles: string[];
    s3_url?: string;
    bedrock_fit_score?: number;
    bedrock_reasoning?: string;
    bedrock_strengths?: string[];
    bedrock_gaps?: string[];
    bedrock_recommendation?: string;
  }>;
}

interface DownloadResponse {
  status: string;
  download_url: string;
  expires_in_seconds: number;
}

interface BatchStatusResponse {
  batch_id: string;
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_files: number;
  processed_files: number;
  failed_files: number;
  completion_percentage: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  errors?: Array<{ timestamp: string; message: string }>;
}

class APIClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = '/api') {
    this.baseURL = baseURL;
    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Error interceptor
    this.client.interceptors.response.use(
      response => response,
      error => {
        console.error('API Error:', error);
        throw error;
      }
    );
  }

  // Job API
  async parseJob(jobDescription: string): Promise<JobParseResponse> {
    const response = await this.client.post<JobParseResponse>('/jobs/parse', {
      job_description: jobDescription,
    });
    return response.data;
  }

  // Get all jobs
  async getJobs(): Promise<AllJobsResponse> {
    const response = await this.client.get<AllJobsResponse>('/jobs');
    return response.data;
  }

  // Resume API
  async uploadResumes(files: File[], jobId: string): Promise<UploadResponse> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('job_id', jobId);

    const response = await this.client.post<UploadResponse>(
      '/resumes/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  }

  // Results API
  async getResults(batchId: string): Promise<ResultsResponse> {
    const response = await this.client.get<ResultsResponse>(
      `/results/${batchId}`
    );
    return response.data;
  }

  // Batch Status API (for polling)
  async getBatchStatus(batchId: string): Promise<BatchStatusResponse> {
    const response = await this.client.get<BatchStatusResponse>(
      `/batches/${batchId}/status`
    );
    return response.data;
  }

  // Download API
  async getDownloadUrl(batchId: string, filename: string): Promise<DownloadResponse> {
    const response = await this.client.get<DownloadResponse>(
      `/download/${batchId}/${encodeURIComponent(filename)}`
    );
    return response.data;
  }

  // Batches API
  async getBatches(): Promise<AllBatchesResponse> {
    const response = await this.client.get<AllBatchesResponse>('/batches');
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.client.get<{ status: string }>('/health');
    return response.data;
  }
}

export default new APIClient();
export type { JobParseResponse, UploadResponse, ResultsResponse, DownloadResponse, BatchStatusResponse, AllJobsResponse, JobData, AllBatchesResponse, BatchSummary };
