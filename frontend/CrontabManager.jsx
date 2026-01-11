import React, { useState, useEffect, useRef } from 'react';
import {
    Play,
    Square,
    Terminal,
    Edit3,
    Save,
    X,
    RefreshCw,
    Cpu,
    Activity,
    Filter,
    Zap,
    Clock,
    ArrowLeft,
    CheckCircle,
    XCircle,
    AlertCircle,
    Calendar,
    FileText,
    Download,
    Copy,
    Maximize2
} from 'lucide-react';
import axios from 'axios';

// --- Sub Components ---

const StatusBadge = ({ exitCode, status, pid }) => {
    if (status === 'running') {
        return (
            <div className="flex flex-col">
                <span className="text-blue-400 animate-pulse font-bold flex items-center gap-1">
                    <RefreshCw size={10} className="animate-spin" />
                    RUNNING
                </span>
                <span className="text-[10px] text-slate-500 font-mono mt-0.5">PID: <span className="text-blue-300">{pid}</span></span>
            </div>
        );
    }
    if (exitCode === 0) return <span className="text-emerald-500 font-bold">EXIT 0</span>;
    if (exitCode === 137) return <span className="text-rose-500 font-bold" title="Killed by Signal 9">SIGKILL</span>;
    if (exitCode === null || exitCode === undefined) return <span className="text-slate-600">PENDING</span>;
    return <span className="text-rose-500 font-bold">EXIT {exitCode}</span>;
};

const TerminalLine = ({ text, type = 'info', jobId }) => {
    const colors = {
        info: 'text-slate-300',
        success: 'text-emerald-400',
        error: 'text-rose-400',
        warn: 'text-yellow-400',
        cmd: 'text-blue-400 font-bold'
    };
    return (
        <div className={`font-mono text-xs py-0.5 border-l-2 border-transparent hover:border-slate-700 pl-2 ${colors[type] || colors.info} flex`}>
            <span className="opacity-30 mr-3 select-none w-16 text-right shrink-0">
                {new Date().toLocaleTimeString('en-US', { hour12: false })}
            </span>
            {jobId && <span className="mr-2 text-slate-600 select-none shrink-0">[{jobId}]</span>}
            <span className="break-all">{text}</span>
        </div>
    );
};

// --- History Log Modal ---
const HistoryLogModal = ({ history, onClose }) => {
    if (!history) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-[#0d1117] border border-[#30363d] w-full max-w-5xl h-[85vh] rounded-xl shadow-2xl flex flex-col overflow-hidden">
                {/* Modal Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#30363d] bg-[#161b22]">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-slate-800 rounded-lg">
                            <FileText size={18} className="text-slate-300" />
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-200 text-sm">Execution Log #{history.id}</h3>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{history.runAt}</div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-[#21262d] hover:bg-[#30363d] text-slate-300 text-xs rounded border border-[#30363d] transition">
                            <Copy size={14} /> Copy
                        </button>
                        <button className="flex items-center gap-2 px-3 py-1.5 bg-[#21262d] hover:bg-[#30363d] text-slate-300 text-xs rounded border border-[#30363d] transition">
                            <Download size={14} /> Save
                        </button>
                        <div className="w-[1px] h-6 bg-[#30363d] mx-1"></div>
                        <button onClick={onClose} className="p-1.5 hover:bg-rose-900/30 hover:text-rose-500 text-slate-400 rounded transition">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Log Content */}
                <div className="flex-1 overflow-auto p-4 bg-[#010409] font-mono text-xs text-slate-300 custom-scrollbar whitespace-pre-wrap leading-relaxed selection:bg-blue-900 selection:text-white">
                    {history.fullLog}
                </div>

                {/* Footer */}
                <div className="px-4 py-2 border-t border-[#30363d] bg-[#161b22] text-[10px] text-slate-500 flex justify-between">
                    <span>Size: {(history.fullLog?.length / 1024).toFixed(2)} KB</span>
                    <span>Encoding: UTF-8</span>
                </div>
            </div>
        </div>
    );
};

// --- Job Detail View Component ---
const JobDetailView = ({ job, onBack, history, onViewLog }) => {
    const successCount = history.filter(h => h.exitCode === 0).length;
    const successRate = history.length > 0 ? Math.round((successCount / history.length) * 100) : 0;

    return (
        <div className="flex-1 flex flex-col bg-[#0d1117] overflow-hidden">
            {/* Detail Header */}
            <div className="p-4 border-b border-[#30363d] flex items-center gap-4 bg-[#161b22]">
                <button
                    onClick={onBack}
                    className="p-2 hover:bg-[#30363d] rounded-full text-slate-400 hover:text-white transition"
                >
                    <ArrowLeft size={18} />
                </button>
                <div>
                    <h2 className="text-slate-200 font-bold text-lg flex items-center gap-2">
                        Job #{job.id}
                        <span className="text-slate-500 text-sm font-normal">({job.schedule})</span>
                    </h2>
                    <p className="text-slate-500 text-xs font-mono mt-1 truncate max-w-2xl">{job.command}</p>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4 p-4">
                <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
                    <div className="text-slate-500 text-xs mb-1">Success Rate</div>
                    <div className={`text-2xl font-bold ${successRate >= 80 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {successRate}%
                    </div>
                </div>
                <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
                    <div className="text-slate-500 text-xs mb-1">Total Runs</div>
                    <div className="text-2xl font-bold text-blue-400">{history.length}</div>
                </div>
                <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
                    <div className="text-slate-500 text-xs mb-1">Avg Duration</div>
                    <div className="text-2xl font-bold text-slate-300">3.2s</div>
                </div>
                <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
                    <div className="text-slate-500 text-xs mb-1">Last Status</div>
                    <div className="mt-1"><StatusBadge exitCode={job.lastExitCode} status={job.status} pid={job.pid} /></div>
                </div>
            </div>

            {/* History Table */}
            <div className="flex-1 overflow-auto px-4 pb-4">
                <h3 className="text-slate-400 text-sm font-bold mb-3 flex items-center gap-2">
                    <Calendar size={14} /> Execution History
                    <span className="text-xs text-slate-600 font-normal ml-2">(Click row to view logs)</span>
                </h3>
                <table className="w-full text-left text-xs border-collapse">
                    <thead className="text-slate-500 font-semibold border-b border-[#30363d]">
                        <tr>
                            <th className="py-2 px-2">Run Time</th>
                            <th className="py-2 px-2">Trigger</th>
                            <th className="py-2 px-2">Duration</th>
                            <th className="py-2 px-2">Exit Code</th>
                            <th className="py-2 px-2 text-right">Log ID</th>
                        </tr>
                    </thead>
                    <tbody className="text-slate-300">
                        {history.map((run) => (
                            <tr
                                key={run.id}
                                onClick={() => onViewLog(run)}
                                className="border-b border-[#21262d] hover:bg-[#1f242c] cursor-pointer transition-colors group"
                            >
                                <td className="py-2.5 px-2 font-mono text-slate-400 group-hover:text-blue-400 transition-colors">{run.runAt}</td>
                                <td className="py-2.5 px-2">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${run.trigger === 'SCHEDULE' ? 'bg-slate-800 text-slate-400' : 'bg-blue-900/30 text-blue-400'}`}>
                                        {run.trigger}
                                    </span>
                                </td>
                                <td className="py-2.5 px-2">{run.duration}</td>
                                <td className="py-2.5 px-2">
                                    {run.exitCode === 0 ? (
                                        <span className="flex items-center gap-1.5 text-emerald-500">
                                            <CheckCircle size={12} /> Success
                                        </span>
                                    ) : run.exitCode === 137 ? (
                                        <span className="flex items-center gap-1.5 text-rose-500">
                                            <Square size={12} /> Killed
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1.5 text-rose-400">
                                            <AlertCircle size={12} /> Failed ({run.exitCode})
                                        </span>
                                    )}
                                </td>
                                <td className="py-2.5 px-2 text-right text-slate-600 font-mono flex items-center justify-end gap-2">
                                    <span className="opacity-0 group-hover:opacity-100 transition-opacity text-blue-400 flex items-center text-[10px] gap-1">
                                        <FileText size={10} /> View Log
                                    </span>
                                    #{run.id}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default function CrontabManager() {
    const [jobs, setJobs] = useState([]);
    const [logs, setLogs] = useState([
        { type: 'info', text: 'Connecting to system...', jobId: null },
    ]);
    const [selectedJobId, setSelectedJobId] = useState(null);
    const [viewingDetailId, setViewingDetailId] = useState(null);
    const [mockHistories, setMockHistories] = useState({});
    const [viewingHistoryLog, setViewingHistoryLog] = useState(null); // State for Modal

    const [editingId, setEditingId] = useState(null);
    const [editForm, setEditForm] = useState({});
    const logEndRef = useRef(null);
    const timersRef = useRef({});

    useEffect(() => {
        // Initial fetch from backend
        axios.get('/api/crontab/jobs')
            .then(res => {
                setJobs(res.data.jobs);
                addLog('Loaded jobs from backend configuration.', 'info');
            })
            .catch(err => {
                addLog(`Failed to load jobs: ${err.message}`, 'error');
            });
    }, []);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs, selectedJobId]);

    const addLog = (text, type = 'info', jobId = null) => {
        setLogs(prev => [...prev.slice(-100), { text, type, jobId }]); // Keep last 100 logs
    };

    const handleRun = (id) => {
        const job = jobs.find(j => j.id === id);
        addLog(`Requesting manual execution for Job #${id}...`, 'info', id);

        // Call backend to trigger (mock) run
        axios.post(`/api/crontab/run/${id}`)
            .then(res => {
                const { pid, status } = res.data;
                setJobs(prev => prev.map(j => j.id === id ? { ...j, status, pid } : j));
                addLog(`Spawned process (PID: ${pid}): ${job.command.substring(0, 50)}...`, 'cmd', id);

                // Polling or waiting for completion simulated here for UI responsiveness
                // In a real websocket setup, we'd listen for events.
                // For this demo, let's just simulate the backend finishing after some time 
                // OR rely on the backend to actually do the timing. 
                // Since the prompt says "mock execution", let's assume the backend will return immediately with "running" 
                // and we simulate the "completion" effect in UI for better UX, or we poll.
                // Let's stick to the user's React code logic for "effect", but sync with backend.

                simulateCompletion(id, pid);
            })
            .catch(err => {
                addLog(`Failed to run job: ${err.response?.data?.error || err.message}`, 'error', id);
            });
    };

    const simulateCompletion = (id, pid) => {
        // This replicates the user's "setTimeout" logic but represents "waiting for backend result"
        const timeoutId = setTimeout(() => {
            // Fetch "latest" status from backend (which would be updated by the mock service)
            // For now, we'll just mock it client side to match the demo feeling directly
            const isSuccess = Math.random() > 0.2;
            const duration = (Math.random() * 5).toFixed(2) + 's';
            const exitCode = isSuccess ? 0 : 1;
            const runDate = new Date().toLocaleString('sv-SE');

            setJobs(prev => prev.map(j => j.id === id ? {
                ...j,
                status: 'idle',
                pid: null,
                lastExitCode: exitCode,
                lastDuration: duration,
                lastRunAt: runDate
            } : j));

            if (isSuccess) {
                addLog(`[PID:${pid}] Process completed successfully. Duration: ${duration}`, 'success', id);
            } else {
                addLog(`[PID:${pid}] Process failed with Exit Code 1. Check stderr for details.`, 'error', id);
            }

            delete timersRef.current[id];
        }, 3000);

        timersRef.current[id] = { timeoutId, pid };
    };

    const handleKill = (id) => {
        if (timersRef.current[id]) {
            clearTimeout(timersRef.current[id].timeoutId);
            delete timersRef.current[id];
        }

        axios.post(`/api/crontab/kill/${id}`)
            .then(res => {
                setJobs(prev => prev.map(j => j.id === id ? {
                    ...j,
                    status: 'idle',
                    pid: null,
                    lastExitCode: 137,
                    lastDuration: 'Terminated',
                    lastRunAt: new Date().toLocaleString('sv-SE')
                } : j));
                addLog(`[PID:?] Received SIGKILL. Process terminated by user.`, 'error', id);
            })
            .catch(err => console.error(err));
    };

    const handleEdit = (job) => {
        setEditingId(job.id);
        setEditForm({ ...job });
    };

    const handleSave = () => {
        // In real app, post to backend
        setJobs(prev => prev.map(j => j.id === editingId ? { ...editForm, id: editingId } : j));
        setEditingId(null);
        addLog(`Crontab updated for job ID: ${editingId}`, 'warn', editingId);
    };

    const toggleEnabled = (id) => {
        setJobs(prev => prev.map(j => {
            if (j.id === id) {
                const newState = !j.enabled;
                addLog(`Job ${id} is now ${newState ? 'ENABLED' : 'DISABLED'}`, 'info', id);
                return { ...j, enabled: newState };
            }
            return j;
        }));
    };

    const handleViewDetail = (e, id) => {
        e.stopPropagation();
        // Simulate fetching history
        if (!mockHistories[id]) {
            // We can keep the user's random history generator for the "Demo" feeling
            setMockHistories(prev => ({ ...prev, [id]: generateMockHistory(id) }));
        }
        setViewingDetailId(id);
        setSelectedJobId(id);
    };

    const handleBackToDashboard = () => {
        setViewingDetailId(null);
        setSelectedJobId(null);
    };

    // User's mock history generator
    const generateMockHistory = (jobId) => {
        return Array.from({ length: 8 }).map((_, i) => {
            const isSuccess = Math.random() > 0.2;
            const date = new Date();
            date.setDate(date.getDate() - i);
            date.setHours(Math.floor(Math.random() * 23), Math.floor(Math.random() * 59));
            const dateStr = date.toLocaleString('sv-SE');

            const logLines = [];
            logLines.push(`[${dateStr}] [INFO] Initializing environment for Job #${jobId}...`);
            for (let j = 0; j < 50; j++) { // Reduced for performance
                const time = new Date(date.getTime() + j * 100).toISOString().split('T')[1].slice(0, -1);
                logLines.push(`[${dateStr} ${time}] [DEBUG] Processing data chunk ...`);
            }

            if (!isSuccess) {
                logLines.push(`[${dateStr}] [ERROR] Connection timed out.`);
                logLines.push(`[${dateStr}] [FATAL] Process terminated.`);
            } else {
                logLines.push(`[${dateStr}] [INFO] Job finished successfully.`);
            }

            return {
                id: 1000 + i,
                runAt: dateStr,
                duration: (Math.random() * 10 + 1).toFixed(1) + 's',
                exitCode: isSuccess ? 0 : 1,
                trigger: Math.random() > 0.3 ? 'SCHEDULE' : 'MANUAL',
                fullLog: logLines.join('\n')
            };
        });
    };

    const visibleLogs = selectedJobId
        ? logs.filter(log => log.jobId === selectedJobId || log.jobId === null)
        : logs;

    const currentDetailJob = viewingDetailId ? jobs.find(j => j.id === viewingDetailId) : null;

    return (
        <div className="h-screen bg-[#0d1117] text-slate-300 font-mono flex flex-col overflow-hidden selection:bg-blue-900 selection:text-white">

            {/* 1. System Header */}
            <header className="h-10 bg-[#161b22] border-b border-[#30363d] flex items-center justify-between px-4 text-xs select-none shrink-0">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 font-bold text-slate-100">
                        <Terminal size={14} />
                        <span>ROOT@TRADING-SERVER:~</span>
                    </div>
                    <div className="h-4 w-[1px] bg-[#30363d]"></div>
                    <div className="flex items-center gap-2 text-slate-500">
                        <Cpu size={12} />
                        <span>Load: 0.24, 0.15, 0.08</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-500">
                        <Activity size={12} />
                        <span>Uptime: 45d 12h</span>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1.5 text-emerald-500">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        crond active
                    </span>
                    <button className="hover:bg-[#30363d] p-1 rounded transition" title="Refresh System Status">
                        <RefreshCw size={12} />
                    </button>
                </div>
            </header>

            {/* 2. Main Workspace (Dynamic Switching) */}
            <div className="flex-1 flex flex-col min-h-0 relative">

                {viewingDetailId && currentDetailJob ? (
                    // Detail View
                    <JobDetailView
                        job={currentDetailJob}
                        history={mockHistories[viewingDetailId] || []}
                        onBack={handleBackToDashboard}
                        onViewLog={(history) => setViewingHistoryLog(history)} // Pass handler
                    />
                ) : (
                    // Dashboard View (Job List)
                    <div className="flex-1 overflow-auto bg-[#0d1117]">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-[#161b22] z-10 text-xs font-semibold text-slate-400 border-b border-[#30363d]">
                                <tr>
                                    <th className="py-2 px-3 w-10 text-center">#</th>
                                    <th className="py-2 px-3 w-10 text-center">On</th>
                                    <th className="py-2 px-3 w-40">Schedule</th>
                                    <th className="py-2 px-3">Command / Comment</th>
                                    <th className="py-2 px-3 w-32">Status / PID</th>
                                    <th className="py-2 px-3 w-32">Last Run</th>
                                    <th className="py-2 px-3 w-32 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="text-xs">
                                {jobs.map((job) => {
                                    const isEditing = editingId === job.id;
                                    const isSelected = selectedJobId === job.id;

                                    return (
                                        <tr
                                            key={job.id}
                                            onClick={() => setSelectedJobId(isSelected ? null : job.id)}
                                            className={`
                        border-b border-[#21262d] transition-colors cursor-pointer group
                        ${isSelected ? 'bg-[#1f242c] border-l-2 border-l-blue-500' : 'hover:bg-[#161b22] border-l-2 border-l-transparent'}
                        ${!job.enabled ? 'opacity-50' : ''}
                      `}
                                        >
                                            <td className="py-2 px-3 text-center text-slate-600 font-mono">{job.id}</td>
                                            <td className="py-2 px-3 text-center">
                                                <input
                                                    type="checkbox"
                                                    checked={job.enabled}
                                                    onClick={(e) => e.stopPropagation()}
                                                    onChange={() => toggleEnabled(job.id)}
                                                    className="accent-blue-500 cursor-pointer"
                                                />
                                            </td>
                                            <td className="py-2 px-3 font-bold text-yellow-500/90 whitespace-nowrap font-mono">
                                                {isEditing ? (
                                                    <input
                                                        className="bg-[#0d1117] border border-slate-600 text-yellow-500 w-full px-1 py-0.5 focus:outline-none focus:border-blue-500"
                                                        value={editForm.schedule}
                                                        onClick={(e) => e.stopPropagation()}
                                                        onChange={e => setEditForm({ ...editForm, schedule: e.target.value })}
                                                    />
                                                ) : job.schedule}
                                            </td>
                                            <td className="py-2 px-3 max-w-lg">
                                                <div className="flex flex-col gap-0.5">
                                                    <div className="text-slate-500 italic truncate">
                                                        {isEditing ? (
                                                            <input
                                                                className="bg-[#0d1117] border border-slate-600 text-slate-500 w-full px-1 py-0.5 focus:outline-none focus:border-blue-500"
                                                                value={editForm.comment}
                                                                onClick={(e) => e.stopPropagation()}
                                                                onChange={e => setEditForm({ ...editForm, comment: e.target.value })}
                                                            />
                                                        ) : job.comment}
                                                    </div>
                                                    <div className="text-slate-300 truncate font-medium font-mono text-[11px]" title={job.command}>
                                                        {isEditing ? (
                                                            <textarea
                                                                className="bg-[#0d1117] border border-slate-600 text-slate-300 w-full px-1 py-0.5 focus:outline-none focus:border-blue-500 resize-none"
                                                                rows={2}
                                                                value={editForm.command}
                                                                onClick={(e) => e.stopPropagation()}
                                                                onChange={e => setEditForm({ ...editForm, command: e.target.value })}
                                                            />
                                                        ) : job.command}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-2 px-3 whitespace-nowrap align-top pt-2.5 font-mono">
                                                <StatusBadge exitCode={job.lastExitCode} status={job.status} pid={job.pid} />
                                                {job.status !== 'running' && job.lastDuration && job.lastDuration !== '-' && (
                                                    <div className="text-[10px] text-slate-500 mt-0.5">Took {job.lastDuration}</div>
                                                )}
                                            </td>
                                            <td className="py-2 px-3 text-[11px] text-slate-400 whitespace-nowrap align-top pt-2.5 font-mono">
                                                <div><span className="text-slate-600 mr-1">L:</span>{job.lastRunAt?.split(' ')[1] || '-'}</div>
                                                <div><span className="text-slate-600 mr-1">N:</span>{job.nextRunAt?.split(' ')[1] || '-'}</div>
                                            </td>
                                            <td className="py-2 px-3 text-right">
                                                {isEditing ? (
                                                    <div className="flex justify-end gap-1">
                                                        <button onClick={(e) => { e.stopPropagation(); handleSave() }} className="p-1.5 bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded"><Save size={14} /></button>
                                                        <button onClick={(e) => { e.stopPropagation(); setEditingId(null) }} className="p-1.5 bg-slate-700/30 text-slate-400 hover:bg-slate-700/50 rounded"><X size={14} /></button>
                                                    </div>
                                                ) : (
                                                    <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                        {job.status === 'running' ? (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleKill(job.id); }}
                                                                className="p-1.5 rounded border border-rose-900/50 bg-rose-950 text-rose-500 hover:bg-rose-900 hover:text-white flex items-center gap-1.5 transition-colors"
                                                                title={`Kill Process (PID: ${job.pid})`}
                                                            >
                                                                <Square size={10} fill="currentColor" />
                                                            </button>
                                                        ) : (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); handleRun(job.id); }}
                                                                disabled={!job.enabled}
                                                                className={`p-1.5 rounded border border-[#30363d] flex items-center gap-1 ${!job.enabled ? 'opacity-30 cursor-not-allowed' : 'hover:bg-[#21262d] hover:border-slate-500 text-slate-300'}`}
                                                                title="Run Now"
                                                            >
                                                                <Play size={12} className={job.status === 'running' ? '' : 'fill-slate-300'} />
                                                            </button>
                                                        )}

                                                        {/* History Button */}
                                                        <button
                                                            onClick={(e) => handleViewDetail(e, job.id)}
                                                            className="p-1.5 rounded border border-[#30363d] hover:bg-[#21262d] hover:border-slate-500 text-slate-300"
                                                            title="View History & Details"
                                                        >
                                                            <Clock size={12} />
                                                        </button>

                                                        <button
                                                            // Disable edit in demo mode if preferred, or allow mock edit
                                                            onClick={(e) => { e.stopPropagation(); handleEdit(job); }}
                                                            className="p-1.5 rounded border border-[#30363d] hover:bg-[#21262d] hover:border-slate-500 text-slate-300"
                                                            title="Edit Crontab Line"
                                                        >
                                                            <Edit3 size={12} />
                                                        </button>
                                                    </div>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>

                        <div className="p-2 border-b border-[#21262d] border-dashed opacity-30 hover:opacity-80 transition cursor-pointer flex items-center gap-2 text-xs">
                            <span className="text-slate-500">+ Add new crontab line...</span>
                        </div>
                    </div>
                )}

                {/* History Log Modal (Overlay) */}
                {viewingHistoryLog && (
                    <HistoryLogModal
                        history={viewingHistoryLog}
                        onClose={() => setViewingHistoryLog(null)}
                    />
                )}

                {/* Bottom Pane: Logs (Always Visible) */}
                <div className="h-48 bg-[#010409] border-t border-[#30363d] flex flex-col shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.5)] shrink-0 z-10">
                    <div className="h-8 bg-[#161b22] border-b border-[#30363d] px-3 flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 text-slate-400">
                            <Terminal size={12} />
                            <span className="font-bold">OUTPUT</span>
                            {selectedJobId ? (
                                <span className="flex items-center gap-1 px-1.5 py-0.5 bg-blue-900/40 border border-blue-800 text-blue-200 rounded text-[10px]">
                                    <Filter size={10} />
                                    Filtering: Job #{selectedJobId}
                                </span>
                            ) : (
                                <span className="text-slate-600 text-[10px]">(All Streams)</span>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <button onClick={() => setLogs([])} className="hover:text-white text-slate-600">Clear</button>
                            <button onClick={() => setSelectedJobId(null)} className={`hover:text-white ${selectedJobId ? 'text-blue-400' : 'text-slate-600'}`}>
                                {selectedJobId ? 'Show All' : 'Show All'}
                            </button>
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-0.5 custom-scrollbar bg-[#010409]">
                        {visibleLogs.length === 0 && (
                            <div className="text-slate-700 italic px-2 pt-2">
                                {selectedJobId ? `No output logs found for Job #${selectedJobId}...` : "Waiting for process output..."}
                            </div>
                        )}
                        {visibleLogs.map((log, i) => (
                            <TerminalLine key={i} text={log.text} type={log.type} jobId={log.jobId} />
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>
            </div>

        </div>
    );
}
