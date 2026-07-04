import React, { useState, useEffect } from 'react';
import api from '../services/api';
import {
  Search, SlidersHorizontal, RefreshCw, X, Eye,
  Play, Terminal, AlertTriangle, ChevronLeft, ChevronRight, FileText
} from 'lucide-react';

const Jobs = () => {
  const [jobs, setJobs] = useState([]);
  const [queues, setQueues] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [queueFilter, setQueueFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Selected Job Details
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [jobDetails, setJobDetails] = useState(null);
  const [jobLogs, setJobLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [aiSummary, setAiSummary] = useState(null);

  const fetchFilters = async () => {
    try {
      const projResp = await api.get('/projects');
      setProjects(projResp.data);
      if (projResp.data.length > 0) {
        const firstProjId = projResp.data[0].id;
        setSelectedProjectId(firstProjId);
        const qResp = await api.get(`/projects/${firstProjId}/queues`);
        setQueues(qResp.data);
      }
    } catch (err) {
      console.error('Failed to fetch projects/queues filters:', err);
    }
  };

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (queueFilter) params.queue_id = queueFilter;

      const response = await api.get('/jobs', { params });

      let filteredJobs = response.data;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        filteredJobs = filteredJobs.filter(j =>
          j.task_name.toLowerCase().includes(query) ||
          j.id.toLowerCase().includes(query)
        );
      }

      setJobs(filteredJobs);
      setCurrentPage(1); // Reset page on filter change
    } catch (err) {
      console.error('Failed to fetch jobs list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [statusFilter, queueFilter, searchQuery, selectedProjectId]);

  const handleProjectChange = async (projectId) => {
    setSelectedProjectId(projectId);
    setQueueFilter('');
    try {
      const response = await api.get(`/projects/${projectId}/queues`);
      setQueues(response.data);
    } catch (err) {
      console.error('Failed to change projects context:', err);
    }
  };

  const handleViewDetails = async (jobId) => {
    setSelectedJobId(jobId);
    setModalLoading(true);
    setAiSummary(null);
    try {
      const [detailResp, logsResp] = await Promise.all([
        api.get(`/jobs/${jobId}`),
        api.get(`/jobs/${jobId}/logs`)
      ]);
      setJobDetails(detailResp.data);
      setJobLogs(logsResp.data);

      const status = detailResp.data.job.status;
      if (['failed', 'dlq', 'cancelled'].includes(status)) {
        try {
          const aiResp = await api.get(`/jobs/${jobId}/ai-summary`);
          setAiSummary(aiResp.data.ai_summary);
        } catch {
          // ignore failure
        }
      }
    } catch (err) {
      console.error('Failed to fetch job details:', err);
    } finally {
      setModalLoading(false);
    }
  };

  const handleCancelJob = async (jobId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to cancel this job? This halts execution.')) return;
    try {
      await api.post(`/jobs/${jobId}/cancel`);
      fetchJobs();
      if (selectedJobId === jobId) {
        handleViewDetails(jobId);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to cancel job');
    }
  };

  const handleRetryJob = async (jobId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to manually re-enqueue this job?')) return;
    try {
      await api.post(`/jobs/${jobId}/retry`);
      fetchJobs();
      if (selectedJobId === jobId) {
        handleViewDetails(jobId);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to retry job');
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'queued':
        return <span className="status-badge status-badge-queued">queued</span>;
      case 'claimed':
        return <span className="status-badge status-badge-claimed">claimed</span>;
      case 'running':
        return <span className="status-badge status-badge-running">running</span>;
      case 'completed':
        return <span className="status-badge status-badge-completed">completed</span>;
      case 'failed':
        return <span className="status-badge status-badge-failed">failed</span>;
      case 'dlq':
        return <span className="status-badge status-badge-dlq">dead-letter</span>;
      case 'cancelled':
        return <span className="status-badge status-badge-cancelled">cancelled</span>;
      default:
        return <span className="status-badge bg-slate-800 text-slate-400">{status}</span>;
    }
  };

  // Pagination bounds
  const totalPages = Math.max(1, Math.ceil(jobs.length / itemsPerPage));
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentJobs = jobs.slice(indexOfFirstItem, indexOfLastItem);

  const renderSkeletons = () => (
    [...Array(5)].map((_, i) => (
      <tr key={i} className="animate-pulse">
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-16" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-32" /></td>
        <td className="p-3"><div className="h-5 bg-slate-800 rounded w-20" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-12" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-28" /></td>
        <td className="p-3"><div className="h-6 bg-slate-800 rounded w-12 ml-auto" /></td>
      </tr>
    ))
  );

  return (
    <div className="space-y-4">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Jobs Dashboard</h1>
          <p className="text-xs text-slate-400 mt-0.5">Monitor job executions, inspect logs, and retry failed operations.</p>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="form-input w-48 bg-[#111827] border-[#1F2937]"
            value={selectedProjectId}
            onChange={(e) => handleProjectChange(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          <button
            onClick={fetchJobs}
            className="p-1.5 rounded border border-[#1F2937] bg-[#111827] hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 rounded-lg border border-[#1F2937] bg-[#111827]">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            className="form-input pl-8"
            placeholder="Search by job ID or task name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div>
          <select
            className="form-input"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="dlq">Failed Jobs (DLQ)</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div>
          <select
            className="form-input"
            value={queueFilter}
            onChange={(e) => setQueueFilter(e.target.value)}
          >
            <option value="">All Queues</option>
            {queues.map((q) => (
              <option key={q.id} value={q.id}>{q.name}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-end text-[10px] text-slate-500 font-bold uppercase tracking-wider">
          Total matched: {jobs.length} records
        </div>
      </div>

      {/* Jobs Table */}
      <div className="panel-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                <th className="table-th">ID</th>
                <th className="table-th">Job Type</th>
                <th className="table-th">Status</th>
                <th className="table-th">Attempts</th>
                <th className="table-th">Scheduled Time</th>
                <th className="table-th text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1F2937]/50">
              {loading ? (
                renderSkeletons()
              ) : currentJobs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-8 text-slate-500 text-xs">
                    No active background jobs matched your search criteria. Try adjusting the status or queue filters.
                  </td>
                </tr>
              ) : (
                currentJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="table-row-hover cursor-pointer"
                    onClick={() => handleViewDetails(job.id)}
                  >
                    <td className="table-td font-mono text-slate-400">{job.id.substring(0, 8)}...</td>
                    <td className="table-td text-white font-medium">{job.task_name}</td>
                    <td className="table-td">{getStatusBadge(job.status)}</td>
                    <td className="table-td font-mono text-slate-400">{job.retry_count} / {job.max_retries}</td>
                    <td className="table-td text-slate-400">{new Date(job.scheduled_at).toLocaleString()}</td>
                    <td className="table-td text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => handleViewDetails(job.id)}
                          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {['queued', 'running'].includes(job.status) && (
                          <button
                            onClick={(e) => handleCancelJob(job.id, e)}
                            className="p-1 rounded hover:bg-red-500/10 text-red-400 cursor-pointer"
                            title="Cancel Job"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {['failed', 'dlq', 'cancelled'].includes(job.status) && (
                          <button
                            onClick={(e) => handleRetryJob(job.id, e)}
                            className="p-1 rounded hover:bg-emerald-500/10 text-emerald-400 cursor-pointer"
                            title="Re-enqueue Job"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        {!loading && jobs.length > 0 && (
          <div className="p-3 bg-gray-900/20 border-t border-[#1F2937] flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing page <span className="font-semibold text-white">{currentPage}</span> of <span className="font-semibold text-white">{totalPages}</span> ({jobs.length} items total)
            </div>
            <div className="flex items-center gap-1">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(prev => prev - 1)}
                className="p-1 rounded bg-[#111827] hover:bg-slate-800 border border-[#1F2937] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(prev => prev + 1)}
                className="p-1 rounded bg-[#111827] hover:bg-slate-800 border border-[#1F2937] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Details Modal */}
      {selectedJobId && (
        <div className="fixed inset-0 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm z-50 p-4">
          <div className="w-full max-w-3xl max-h-[90vh] bg-[#111827] rounded-xl border border-[#1F2937] shadow-2xl overflow-hidden flex flex-col">
            <div className="p-4 border-b border-[#1F2937] flex items-center justify-between bg-gray-900/40">
              <div>
                <h3 className="text-sm font-semibold text-white">Job Details</h3>
                <span className="text-[10px] font-mono text-slate-500">{selectedJobId}</span>
              </div>
              <button
                onClick={() => setSelectedJobId(null)}
                className="text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalLoading ? (
              <div className="flex py-12 justify-center flex-grow">
                <span className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : jobDetails ? (
              <div className="overflow-y-auto p-5 space-y-5 flex-grow">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-[#0B0F19] p-3 rounded-lg border border-[#1F2937]">
                    <span className="text-slate-500 text-[9px] uppercase font-bold tracking-wider">Current Status</span>
                    <div className="mt-1">{getStatusBadge(jobDetails.job.status)}</div>
                  </div>
                  <div className="bg-[#0B0F19] p-3 rounded-lg border border-[#1F2937]">
                    <span className="text-slate-500 text-[9px] uppercase font-bold tracking-wider">Max Retries Attempted</span>
                    <p className="text-xs font-semibold text-white mt-1">
                      {jobDetails.job.retry_count} / {jobDetails.job.max_retries}
                    </p>
                  </div>
                  <div className="bg-[#0B0F19] p-3 rounded-lg border border-[#1F2937]">
                    <span className="text-slate-500 text-[9px] uppercase font-bold tracking-wider">Retry Policy</span>
                    <p className="text-xs font-semibold text-white mt-1 capitalize">
                      {jobDetails.job.retry_strategy} (Factor: {jobDetails.job.backoff_factor})
                    </p>
                  </div>
                </div>

                {/* AI Failure Summary display */}
                {aiSummary && (
                  <div className="bg-emerald-600/5 border border-emerald-500/20 p-4 rounded-lg space-y-1">
                    <h4 className="text-[10px] font-bold text-blue-400 uppercase tracking-wider">AI Failure Diagnostics</h4>
                    <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">{aiSummary}</p>
                  </div>
                )}

                {/* Payload Display */}
                <div>
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Job Parameters (JSON)</h4>
                  <pre className="bg-[#0B0F19] p-3 rounded-lg border border-[#1F2937] text-[10px] text-blue-400 font-mono overflow-x-auto max-h-40">
                    {JSON.stringify(jobDetails.job.payload, null, 2)}
                  </pre>
                </div>

                {/* Runs history */}
                <div>
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Execution History</h4>
                  {jobDetails.executions.length === 0 ? (
                    <p className="text-slate-500 text-xs">No attempt runs have executed yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {jobDetails.executions.map((exec) => (
                        <div key={exec.id} className="p-3 rounded-lg border border-[#1F2937] bg-gray-900/20 space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded ${exec.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                              {exec.status}
                            </span>
                            <span className="text-[9px] text-slate-500 font-mono">Run: {exec.id.substring(0, 8)}</span>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400">
                            <div>Started: {new Date(exec.started_at).toLocaleString()}</div>
                            <div>Completed: {exec.completed_at ? new Date(exec.completed_at).toLocaleString() : 'N/A'}</div>
                          </div>

                          {exec.result && (
                            <pre className="bg-[#0B0F19] p-2 rounded text-[9px] text-emerald-400 overflow-x-auto">
                              Result: {JSON.stringify(exec.result)}
                            </pre>
                          )}

                          {exec.error && (
                            <pre className="bg-red-950/20 border border-red-500/10 p-2 rounded text-[9px] text-red-400 overflow-x-auto max-h-24 font-mono">
                              {exec.error}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Stdout / Execution logs */}
                <div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Terminal className="w-3.5 h-3.5 text-blue-500" />
                    <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Execution Logs</h4>
                  </div>
                  {jobLogs.length === 0 ? (
                    <p className="text-slate-500 text-xs">No console logs recorded for this job.</p>
                  ) : (
                    <div className="bg-[#0B0F19] border border-[#1F2937] rounded-lg p-3 font-mono text-[10px] text-slate-300 space-y-1 max-h-48 overflow-y-auto">
                      {jobLogs.map((log) => (
                        <div key={log.id} className="flex gap-2">
                          <span className="text-slate-500">[{new Date(log.created_at).toLocaleTimeString()}]</span>
                          <span className={log.level === 'ERROR' ? 'text-red-400' : log.level === 'WARNING' ? 'text-yellow-400' : 'text-slate-400'}>
                            {log.level}:
                          </span>
                          <span>{log.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : null}

            <div className="p-4 border-t border-[#1F2937] bg-gray-900/40 flex justify-end gap-2">
              {jobDetails && ['failed', 'dlq', 'cancelled'].includes(jobDetails.job.status) && (
                <button
                  onClick={(e) => handleRetryJob(jobDetails.job.id, e)}
                  className="py-1.5 px-3 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs cursor-pointer flex items-center gap-1"
                >
                  <Play className="w-3 h-3" /> Retry Job
                </button>
              )}
              {jobDetails && ['queued', 'running'].includes(jobDetails.job.status) && (
                <button
                  onClick={(e) => handleCancelJob(jobDetails.job.id, e)}
                  className="py-1.5 px-3 rounded bg-red-600 hover:bg-red-500 text-white font-medium text-xs cursor-pointer"
                >
                  Cancel Active
                </button>
              )}
              <button
                onClick={() => setSelectedJobId(null)}
                className="py-1.5 px-3 rounded border border-[#1F2937] hover:bg-slate-800 text-slate-300 text-xs cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Jobs;
