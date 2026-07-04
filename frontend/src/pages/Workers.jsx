import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { Cpu, RefreshCw, Layers, Terminal, Server, Clock, Activity } from 'lucide-react';

const Workers = () => {
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchWorkers = async () => {
    setLoading(true);
    try {
      const response = await api.get('/workers');
      setWorkers(response.data);
    } catch (err) {
      console.error('Failed to fetch workers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkers();
    
    // Poll every 5 seconds
    const interval = setInterval(fetchWorkers, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIndicator = (worker) => {
    const heartbeatTime = new Date(worker.last_heartbeat).getTime();
    const timeDiffSec = (Date.now() - heartbeatTime) / 1000;
    
    // Check if worker went silent for >30 seconds or status is offline
    const isOffline = worker.status === 'offline' || timeDiffSec > 30;

    if (isOffline) {
      return (
        <span className="flex items-center gap-1 text-[10px] text-slate-500 border border-slate-800 bg-slate-900/60 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-500" /> Offline
        </span>
      );
    }
    
    if (worker.status === 'active') {
      return (
        <span className="flex items-center gap-1 text-[10px] text-amber-400 border border-amber-500/10 bg-amber-500/10 px-2 py-0.5 rounded font-bold uppercase tracking-wider animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Processing
        </span>
      );
    }

    return (
      <span className="flex items-center gap-1 text-[10px] text-emerald-400 border border-emerald-500/10 bg-emerald-500/10 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping absolute" style={{ width: '6px', height: '6px' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 relative" /> Listening
      </span>
    );
  };

  const getFriendlyUptime = (startedAt) => {
    const started = new Date(startedAt).getTime();
    const diffMs = Date.now() - started;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just started';
    if (diffMins < 60) return `${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    return `${diffHours}h ${mins}m`;
  };

  if (loading && workers.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-6 w-48 skeleton" />
            <div className="h-3.5 w-72 skeleton" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="panel-card p-5 h-44 skeleton" />
          ))}
        </div>
      </div>
    );
  }

  const activeCount = workers.filter(w => {
    const heartbeatTime = new Date(w.last_heartbeat).getTime();
    const timeDiffSec = (Date.now() - heartbeatTime) / 1000;
    return w.status !== 'offline' && timeDiffSec <= 30;
  }).length;

  return (
    <div className="space-y-4">
      {/* Header section */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Connected Workers</h1>
          <p className="text-xs text-slate-400 mt-0.5">Monitor real-time worker nodes pool capacity, thread concurrency caps, and active task consumption.</p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-[#111827] border border-[#1F2937] px-2.5 py-1 rounded">
            Online Workers: {activeCount} / {workers.length}
          </span>
          <button
            onClick={fetchWorkers}
            className="p-1.5 rounded border border-[#1F2937] bg-[#111827] hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Workers Grid */}
      {workers.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-xs panel-card">
          No worker instances are currently connected to the cluster. Run <code>python -m app.worker.engine</code> to spin up a worker node.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {workers.map((worker) => (
            <div key={worker.id} className="panel-card p-4 flex flex-col justify-between space-y-4">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <Server className="w-4 h-4 text-slate-400" />
                    <h3 className="font-semibold text-sm text-white">{worker.name}</h3>
                  </div>
                  <p className="text-[9px] font-mono text-slate-500">{worker.id.substring(0, 8)}...</p>
                </div>
                {getStatusIndicator(worker)}
              </div>

              {/* Concurrency and System details */}
              <div className="bg-[#0B0F19] p-3 rounded-lg border border-[#1F2937] text-xs space-y-2">
                <div className="flex justify-between items-center text-slate-400">
                  <span className="text-[10px] uppercase font-bold tracking-wider flex items-center gap-1"><Cpu className="w-3 h-3" /> System Platform</span>
                  <span className="font-semibold text-slate-200 font-mono text-[10px]">{worker.system_info?.platform || 'Unknown'}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span className="text-[10px] uppercase font-bold tracking-wider flex items-center gap-1"><Layers className="w-3 h-3" /> Execution Threads Limit</span>
                  <span className="font-semibold text-slate-200 font-mono text-[10px]">{worker.system_info?.max_workers || 5} Jobs</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span className="text-[10px] uppercase font-bold tracking-wider flex items-center gap-1">Process ID (PID)</span>
                  <span className="font-semibold text-slate-200 font-mono text-[10px]">{worker.system_info?.pid || 'N/A'}</span>
                </div>
              </div>

              {/* Uptime and Heartbeat values */}
              <div className="text-[10px] text-slate-500 flex items-center justify-between pt-2 border-t border-[#1F2937]/60">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Uptime: {getFriendlyUptime(worker.started_at)}</span>
                <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> Last Active: {new Date(worker.last_heartbeat).toLocaleTimeString()}</span>
              </div>

            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Workers;
