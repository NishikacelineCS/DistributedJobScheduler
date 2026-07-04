import React, { useState, useEffect } from 'react';
import api from '../services/api';
import {
  Activity, Cpu, CheckCircle2, AlertTriangle, Play,
  RefreshCw, Layers, Clock, AlertOctagon, Terminal, Plus
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [queues, setQueues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');

  // Predefined tasks for rapid submission shortcut
  const [taskName, setTaskName] = useState('send_email');
  const [taskPayload, setTaskPayload] = useState('{\n  "email": "recipient@company.com",\n  "subject": "Rapid Test",\n  "body": "This is enqueued from dashboard!"\n}');

  // Workspace configuration forms state
  const [newProjectName, setNewProjectName] = useState('');
  const [newQueueName, setNewQueueName] = useState('');
  const [newQueuePriority, setNewQueuePriority] = useState('10');
  const [newQueueConcurrency, setNewQueueConcurrency] = useState('10');
  const [creationMessage, setCreationMessage] = useState('');
  const [creationSubmitting, setCreationSubmitting] = useState(false);

  const fetchStats = async () => {
    try {
      const response = await api.get('/workers/stats');
      setStats(response.data);
    } catch (err) {
      console.error('Failed to fetch system stats:', err);
    }
  };

  const fetchProjectsAndQueues = async () => {
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
      console.error('Failed to load projects/queues context:', err);
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchProjectsAndQueues()]);
      setLoading(false);
    };
    init();

    // Set up polling intervals
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleProjectChange = async (projectId) => {
    setSelectedProjectId(projectId);
    try {
      const response = await api.get(`/projects/${projectId}/queues`);
      setQueues(response.data);
    } catch (err) {
      console.error('Failed to load queues for project:', err);
    }
  };

  const handleQuickTrigger = async (e) => {
    e.preventDefault();
    if (queues.length === 0) {
      setMessage('Create a queue first before triggering jobs.');
      return;
    }

    setTriggering(true);
    setMessage('');

    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(taskPayload);
      } catch {
        setMessage('Invalid JSON payload structure.');
        setTriggering(false);
        return;
      }

      const defaultQueueId = queues[0].id; // Trigger onto first queue in selected project
      await api.post('/jobs', {
        task_name: taskName,
        payload: parsedPayload,
        queue_id: defaultQueueId,
        retry_strategy: 'exponential',
        max_retries: 3
      });
      setMessage('Job enqueued successfully!');
      fetchStats();
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Failed to trigger task.');
    } finally {
      setTriggering(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    setCreationSubmitting(true);
    setCreationMessage('');
    try {
      const resp = await api.post('/projects', { name: newProjectName });
      setCreationMessage(`Project "${newProjectName}" created successfully!`);
      setNewProjectName('');

      const projResp = await api.get('/projects');
      setProjects(projResp.data);
      if (resp.data && resp.data.id) {
        setSelectedProjectId(resp.data.id);
        const qResp = await api.get(`/projects/${resp.data.id}/queues`);
        setQueues(qResp.data);
      }
    } catch (err) {
      setCreationMessage(err.response?.data?.detail || 'Failed to create project.');
    } finally {
      setCreationSubmitting(false);
    }
  };

  const handleCreateQueue = async (e) => {
    e.preventDefault();
    if (!newQueueName.trim() || !selectedProjectId) {
      setCreationMessage('Please enter a queue name and select an active project.');
      return;
    }
    setCreationSubmitting(true);
    setCreationMessage('');
    try {
      await api.post(`/projects/${selectedProjectId}/queues`, {
        name: newQueueName,
        priority: parseInt(newQueuePriority),
        concurrency_limit: parseInt(newQueueConcurrency)
      });
      setCreationMessage(`Queue "${newQueueName}" configured successfully!`);
      setNewQueueName('');
      setNewQueuePriority('10');
      setNewQueueConcurrency('10');

      const response = await api.get(`/projects/${selectedProjectId}/queues`);
      setQueues(response.data);
    } catch (err) {
      setCreationMessage(err.response?.data?.detail || 'Failed to configure queue.');
    } finally {
      setCreationSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-6 w-48 skeleton" />
            <div className="h-3.5 w-72 skeleton" />
          </div>
          <div className="h-9 w-36 skeleton" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="p-5 rounded-lg border border-gray-800 bg-[#111827] h-20 skeleton" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="h-72 border border-gray-800 bg-[#111827] rounded-lg lg:col-span-2 skeleton" />
          <div className="h-72 border border-gray-800 bg-[#111827] rounded-lg skeleton" />
        </div>
      </div>
    );
  }

  const chartData = stats ? [
    { name: 'Queued', value: stats.queue_summary.total_queued, color: '#3B82F6' },
    { name: 'Running', value: stats.queue_summary.total_running, color: '#F59E0B' },
    { name: 'Completed', value: stats.queue_summary.total_completed, color: '#10B981' },
    { name: 'Failed', value: stats.queue_summary.total_failed, color: '#EF4444' },
    { name: 'DLQ', value: stats.queue_summary.total_dlq, color: '#F43F5E' }
  ] : [];

  return (
    <div className="space-y-4">
      {/* Dashboard header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">System Dashboard</h1>
          <p className="text-xs text-slate-400 mt-0.5">Monitor active workers, running jobs, and task queue completion states in real-time.</p>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="form-input w-48 bg-[#111827] border-[#1F2937]"
            value={selectedProjectId}
            onChange={(e) => handleProjectChange(e.target.value)}
          >
            {projects.length === 0 && <option value="">No Active Projects</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          <button
            onClick={fetchStats}
            className="p-1.5 rounded border border-[#1F2937] bg-[#111827] hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Workers */}
        <div className="panel-card p-4 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Active Workers</span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-semibold text-white font-mono">{stats?.online_workers || 0}</span>
              <span className="text-[10px] text-emerald-500 font-semibold flex items-center gap-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping inline-block" /> Online
              </span>
            </div>
          </div>
          <div className="bg-emerald-600/10 p-2.5 rounded-md border border-emerald-500/20 text-blue-400">
            <Cpu className="w-4 h-4" />
          </div>
        </div>

        {/* Active Tasks */}
        <div className="panel-card p-4 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Running Jobs</span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-semibold text-white font-mono">{stats?.active_jobs || 0}</span>
              <span className="text-[9px] text-slate-500 block uppercase font-bold tracking-wider">Active</span>
            </div>
          </div>
          <div className="bg-amber-500/10 p-2.5 rounded-md border border-amber-500/20 text-amber-500">
            <Activity className="w-4 h-4" />
          </div>
        </div>

        {/* Throughput */}
        <div className="panel-card p-4 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Completed Jobs (1h)</span>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-semibold text-white font-mono">{stats?.throughput_last_hour || 0}</span>
              <span className="text-[10px] text-emerald-400 font-semibold block">Processed</span>
            </div>
          </div>
          <div className="bg-emerald-500/10 p-2.5 rounded-md border border-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        </div>

        {/* Dead Letter Queue */}
        <div className="panel-card p-4 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Failed Jobs (DLQ)</span>
            <div className="flex items-baseline gap-1.5">
              <span className={`text-2xl font-semibold font-mono ${stats?.queue_summary.total_dlq > 0 ? 'text-red-500' : 'text-white'}`}>
                {stats?.queue_summary.total_dlq || 0}
              </span>
              <span className="text-[9px] text-slate-500 block uppercase font-bold tracking-wider">Needs Attention</span>
            </div>
          </div>
          <div className={`p-2.5 rounded-md border ${stats?.queue_summary.total_dlq > 0 ? 'bg-red-500/10 border-red-500/20 text-red-500' : 'bg-slate-800/60 border-slate-700/60 text-slate-400'}`}>
            <AlertTriangle className="w-4 h-4" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Queue depths summary chart */}
        <div className="panel-card p-4 lg:col-span-2 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Job Status Breakdown</h3>
            <p className="text-[10px] text-slate-500">Real-time overview of current job states across this project.</p>
          </div>

          <div className="h-60 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '4px' }}
                  labelStyle={{ color: '#f1f5f9', fontSize: '10px', fontWeight: 'bold' }}
                  itemStyle={{ fontSize: '10px' }}
                />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right Stack Column */}
        <div className="space-y-6">
          {/* Quick Trigger Tool */}
          <div className="panel-card p-4 space-y-3">
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Play className="w-3 h-3 text-blue-500" /> Trigger Test Job
              </h3>
              <p className="text-[10px] text-slate-500 mt-0.5">Quickly enqueue a task to verify worker execution and database lock handling.</p>
            </div>

            {message && (
              <div className={`text-[10px] p-2 rounded border font-medium ${message.includes('successfully') ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
                {message}
              </div>
            )}

            <form onSubmit={handleQuickTrigger} className="space-y-3">
              <div>
                <label className="form-label">Select Job Type</label>
                <select
                  className="form-input"
                  value={taskName}
                  onChange={(e) => {
                    setTaskName(e.target.value);
                    if (e.target.value === 'send_email') {
                      setTaskPayload('{\n  "email": "recipient@company.com",\n  "subject": "Rapid Test",\n  "body": "This is enqueued from dashboard!"\n}');
                    } else if (e.target.value === 'process_video') {
                      setTaskPayload('{\n  "video_id": "vid_9948",\n  "format": "mp4",\n  "resolution": "1080p"\n}');
                    } else {
                      setTaskPayload('{\n  "fail_rate": 0.6\n}');
                    }
                  }}
                >
                  <option value="send_email">send_email (Simulated SMTP)</option>
                  <option value="process_video">process_video (Video transcoding)</option>
                  <option value="random_fail">random_fail (Random error trigger)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Job Arguments (JSON)</label>
                <textarea
                  rows="3"
                  className="form-input font-mono"
                  value={taskPayload}
                  onChange={(e) => setTaskPayload(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={triggering || queues.length === 0}
                className="w-full py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 active:bg-blue-700 text-white font-medium flex items-center justify-center gap-1.5 transition-all cursor-pointer text-xs disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {triggering ? (
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" /> Enqueue Task
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Tenant Workspace Config Card */}
          <div className="panel-card p-4 space-y-3">
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Plus className="w-3 h-3 text-blue-500" /> Configure Project & Queues
              </h3>
              <p className="text-[10px] text-slate-500 mt-0.5">Create project containers and priority task routing queues.</p>
            </div>

            {creationMessage && (
              <div className={`text-[10px] p-2 rounded border font-medium ${creationMessage.includes('successfully') ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-emerald-500/10 border-emerald-500/20 text-blue-400'}`}>
                {creationMessage}
              </div>
            )}

            <div className="space-y-3 pt-1">
              {/* Project Creation Form */}
              <form onSubmit={handleCreateProject} className="space-y-1.5 border-b border-[#1F2937] pb-3">
                <label className="form-label">Register New Project</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    className="form-input flex-1"
                    placeholder="Enter project name..."
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                  />
                  <button
                    type="submit"
                    disabled={creationSubmitting}
                    className="px-3 rounded bg-[#1F2937] hover:bg-slate-800 text-white font-semibold text-xs cursor-pointer border border-slate-700/60"
                  >
                    Add
                  </button>
                </div>
              </form>

              {/* Queue Creation Form */}
              <form onSubmit={handleCreateQueue} className="space-y-2">
                <label className="form-label">Configure Task Queue</label>
                <div className="space-y-2">
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Enter queue name..."
                    value={newQueueName}
                    onChange={(e) => setNewQueueName(e.target.value)}
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[8px] font-bold text-slate-500 uppercase tracking-wider block mb-0.5">Priority (1-100)</label>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        className="form-input"
                        value={newQueuePriority}
                        onChange={(e) => setNewQueuePriority(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-[8px] font-bold text-slate-500 uppercase tracking-wider block mb-0.5">Max Concurrent Jobs</label>
                      <input
                        type="number"
                        min="1"
                        className="form-input"
                        value={newQueueConcurrency}
                        onChange={(e) => setNewQueueConcurrency(e.target.value)}
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={creationSubmitting || !selectedProjectId}
                    className="w-full py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs cursor-pointer disabled:opacity-50"
                  >
                    Configure Queue
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
