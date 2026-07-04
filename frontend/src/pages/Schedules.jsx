import React, { useState, useEffect } from 'react';
import api from '../services/api';
import {
  Calendar, Layers, Clock, ToggleLeft, ToggleRight,
  Trash2, Plus, X, Play, RefreshCw, HelpCircle, Check
} from 'lucide-react';

const Schedules = () => {
  const [schedules, setSchedules] = useState([]);
  const [queues, setQueues] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');

  // Create schedule Form State
  const [showAddForm, setShowAddForm] = useState(false);
  const [name, setName] = useState('');
  const [taskName, setTaskName] = useState('send_email');
  const [cronExpression, setCronExpression] = useState('');
  const [intervalSeconds, setIntervalSeconds] = useState('');
  const [payload, setPayload] = useState('{}');
  const [selectedQueueId, setSelectedQueueId] = useState('');

  const [loading, setLoading] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const fetchContext = async () => {
    try {
      const projResp = await api.get('/projects');
      setProjects(projResp.data);
      if (projResp.data.length > 0) {
        const firstProjId = projResp.data[0].id;
        setSelectedProjectId(firstProjId);
        await fetchQueues(firstProjId);
      }
    } catch (err) {
      console.error('Failed to load project context:', err);
    }
  };

  const fetchQueues = async (projectId) => {
    try {
      const qResp = await api.get(`/projects/${projectId}/queues`);
      setQueues(qResp.data);
      if (qResp.data.length > 0) {
        setSelectedQueueId(qResp.data[0].id);
      } else {
        setSelectedQueueId('');
      }
    } catch (err) {
      console.error('Failed to fetch queues:', err);
    }
  };

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const response = await api.get('/schedules');
      setSchedules(response.data);
    } catch (err) {
      console.error('Failed to fetch schedules:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContext();
    fetchSchedules();
  }, []);

  const handleProjectChange = async (projectId) => {
    setSelectedProjectId(projectId);
    await fetchQueues(projectId);
  };

  const handleToggleSchedule = async (scheduleId, currentStatus) => {
    try {
      await api.put(`/schedules/${scheduleId}/toggle`, {
        is_active: !currentStatus
      });
      fetchSchedules();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to toggle schedule state');
    }
  };

  const handleDeleteSchedule = async (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this cron schedule definition? This action cannot be undone.')) return;
    try {
      await api.delete(`/schedules/${scheduleId}`);
      fetchSchedules();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete schedule');
    }
  };

  const handleCreateSchedule = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setFormSubmitting(true);

    if (!selectedQueueId) {
      setErrorMsg('Select a target queue first.');
      setFormSubmitting(false);
      return;
    }

    if (!cronExpression && !intervalSeconds) {
      setErrorMsg('Specify either a cron expression (e.g. */5 * * * *) OR interval seconds (e.g. 60).');
      setFormSubmitting(false);
      return;
    }

    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(payload);
      } catch {
        setErrorMsg('Invalid JSON format in payload arguments.');
        setFormSubmitting(false);
        return;
      }

      await api.post('/schedules', {
        queue_id: selectedQueueId,
        name,
        task_name: taskName,
        cron_expression: cronExpression || null,
        interval_seconds: intervalSeconds ? parseInt(intervalSeconds) : null,
        payload: parsedPayload
      });

      // Clear Form and reload
      setName('');
      setCronExpression('');
      setIntervalSeconds('');
      setPayload('{}');
      setShowAddForm(false);
      fetchSchedules();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create schedule.');
    } finally {
      setFormSubmitting(false);
    }
  };

  // Simple translation helper to translate common expressions
  const getCronDescription = (cron) => {
    if (!cron) return '';
    const clean = cron.trim();
    if (clean === '*/5 * * * *') return 'Runs every 5 minutes';
    if (clean === '0 * * * *') return 'Runs every hour at minute 0';
    if (clean === '0 0 * * *') return 'Runs daily at midnight (00:00)';
    if (clean === '0 12 * * 1-5') return 'Runs at 12:00 PM, Monday through Friday';
    return 'Custom expression pattern';
  };

  const renderSkeletons = () => (
    [...Array(3)].map((_, i) => (
      <tr key={i} className="animate-pulse">
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-28" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-24" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-32" /></td>
        <td className="p-3"><div className="h-3.5 bg-slate-800 rounded w-20" /></td>
        <td className="p-3"><div className="h-5 bg-slate-800 rounded w-12" /></td>
        <td className="p-3"><div className="h-6 bg-slate-800 rounded w-12 ml-auto" /></td>
      </tr>
    ))
  );

  return (
    <div className="space-y-4">
      {/* Header section */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Recurring Jobs</h1>
          <p className="text-xs text-slate-400 mt-0.5">Set up automated schedules using interval periods or standard cron definitions.</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm(true)}
            className="py-1.5 px-3 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs flex items-center gap-1 cursor-pointer shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" /> New Schedule
          </button>
          <button
            onClick={fetchSchedules}
            className="p-1.5 rounded border border-[#1F2937] bg-[#111827] hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Schedules Table */}
      <div className="panel-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                <th className="table-th">Name</th>
                <th className="table-th">Job Type</th>
                <th className="table-th">Frequency</th>
                <th className="table-th">Last Run</th>
                <th className="table-th">Next Run</th>
                <th className="table-th">Status</th>
                <th className="table-th text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1F2937]/50">
              {loading ? (
                renderSkeletons()
              ) : schedules.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-slate-500 text-xs">
                    No active recurrent schedules configured. Click "New Schedule" above to add one.
                  </td>
                </tr>
              ) : (
                schedules.map((sched) => (
                  <tr key={sched.id} className="table-row-hover">
                    <td className="table-td text-white font-medium">{sched.name}</td>
                    <td className="table-td text-blue-400 font-mono text-[10px]">{sched.task_name}</td>
                    <td className="table-td">
                      <div className="flex flex-col gap-0.5">
                        <span className="font-semibold text-slate-200">
                          {sched.cron_expression ? `Cron: ${sched.cron_expression}` : `Interval: ${sched.interval_seconds}s`}
                        </span>
                        {sched.cron_expression && (
                          <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">
                            {getCronDescription(sched.cron_expression)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="table-td text-slate-400 font-mono text-[10px]">
                      {sched.last_run_at ? new Date(sched.last_run_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="table-td text-slate-400 font-mono text-[10px]">
                      {sched.is_active && sched.next_run_at ? new Date(sched.next_run_at).toLocaleString() : 'N/A'}
                    </td>
                    <td className="table-td">
                      <button
                        onClick={() => handleToggleSchedule(sched.id, sched.is_active)}
                        className="cursor-pointer transition-transform duration-100 hover:scale-105"
                      >
                        {sched.is_active ? (
                          <span className="status-badge status-badge-completed flex items-center gap-1"><Check className="w-2.5 h-2.5" /> active</span>
                        ) : (
                          <span className="status-badge status-badge-cancelled">paused</span>
                        )}
                      </button>
                    </td>
                    <td className="table-td text-right">
                      <button
                        onClick={() => handleDeleteSchedule(sched.id)}
                        className="p-1 rounded hover:bg-red-500/10 text-red-400 cursor-pointer"
                        title="Delete Schedule"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Schedule Modal */}
      {showAddForm && (
        <div className="fixed inset-0 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm z-50 p-4">
          <div className="w-full max-w-lg bg-[#111827] rounded-xl border border-[#1F2937] shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-[#1F2937] flex items-center justify-between bg-gray-900/40">
              <h3 className="text-sm font-semibold text-white">Create Recurrent Schedule</h3>
              <button
                onClick={() => { setShowAddForm(false); setErrorMsg(''); }}
                className="text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {errorMsg && (
              <div className="mx-4 mt-4 bg-red-500/10 border border-red-500/20 text-red-400 text-xs p-2.5 rounded-lg">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleCreateSchedule} className="p-4 space-y-4">
              <div>
                <label className="form-label">Routing Target (Project/Queue)</label>
                <div className="grid grid-cols-2 gap-3">
                  <select
                    className="form-input"
                    value={selectedProjectId}
                    onChange={(e) => handleProjectChange(e.target.value)}
                  >
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>

                  <select
                    className="form-input"
                    value={selectedQueueId}
                    onChange={(e) => setSelectedQueueId(e.target.value)}
                  >
                    {queues.length === 0 && <option value="">No Queues Configured</option>}
                    {queues.map((q) => (
                      <option key={q.id} value={q.id}>{q.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="form-label">Name</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  placeholder="e.g. Nightly User DB Cleanup"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="form-label">Select Job Type</label>
                  <select
                    className="form-input"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                  >
                    <option value="send_email">send_email (Simulated SMTP)</option>
                    <option value="process_video">process_video (Video transcoding)</option>
                    <option value="random_fail">random_fail (Random error trigger)</option>
                  </select>
                </div>

                <div>
                  <label className="form-label flex items-center gap-1">
                    Timing Trigger <HelpCircle className="w-3 h-3 text-slate-500" title="Fill one field, clear the other" />
                  </label>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Cron: */5 * * * *"
                      value={cronExpression}
                      onChange={(e) => {
                        setCronExpression(e.target.value);
                        setIntervalSeconds('');
                      }}
                    />
                    <input
                      type="number"
                      className="form-input"
                      placeholder="Interval: seconds"
                      value={intervalSeconds}
                      onChange={(e) => {
                        setIntervalSeconds(e.target.value);
                        setCronExpression('');
                      }}
                    />
                  </div>
                  {cronExpression && (
                    <span className="text-[8px] font-semibold text-cyan-400 mt-1 block tracking-tight uppercase">
                      💡 {getCronDescription(cronExpression)}
                    </span>
                  )}
                </div>
              </div>

              <div>
                <label className="form-label">Job Parameters (JSON)</label>
                <textarea
                  rows="3"
                  className="form-input font-mono"
                  placeholder="{}"
                  value={payload}
                  onChange={(e) => setPayload(e.target.value)}
                />
              </div>

              <div className="pt-3 border-t border-[#1F2937] flex justify-end gap-2 bg-gray-900/10 -mx-4 -mb-4 p-4">
                <button
                  type="button"
                  onClick={() => { setShowAddForm(false); setErrorMsg(''); }}
                  className="py-1.5 px-3 rounded border border-[#1F2937] hover:bg-slate-800 text-slate-300 text-xs cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="py-1.5 px-3 rounded bg-[#2563EB] hover:bg-blue-500 text-white font-medium text-xs cursor-pointer disabled:opacity-50"
                >
                  {formSubmitting ? 'Saving...' : 'Save Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Schedules;
