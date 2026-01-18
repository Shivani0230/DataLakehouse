// src/pages/UserDashboard.jsx
import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import FileUpload from '../components/FileUpload';
import FileList from '../components/FileList';
import { dashboardAPI } from '../services/api';
import { FileText, Activity, CloudUpload, RefreshCw } from 'lucide-react';

const UserDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    setRefreshing(true);
    try {
      const [metricsRes, filesRes] = await Promise.all([
        dashboardAPI.getMetrics(),
        dashboardAPI.getFiles()
      ]);
      setMetrics(metricsRes.data);
      setFiles(filesRes.data.files || filesRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return (
    <div className="min-h-screen bg-[#0f172a] text-white flex items-center justify-center">
      <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0f172a] text-white">
      <Navbar />

      <main className="max-w-7xl mx-auto p-8">
        <header className="flex flex-col md:flex-row md:items-center justify-between mb-10">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              My Workspace
            </h2>
            <p className="text-gray-400 mt-2">Manage your private data assets and uploads</p>
          </div>
          <button
            onClick={fetchData}
            disabled={refreshing}
            className="mt-4 md:mt-0 flex items-center px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </header>

        {/* User Metrics */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-gray-800/40 backdrop-blur-md border border-gray-700/50 p-6 rounded-2xl">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
                <FileText className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-gray-400 text-sm font-medium">My Total Files</h3>
                <p className="text-3xl font-bold text-white">{metrics?.total_documents || 0}</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/40 backdrop-blur-md border border-gray-700/50 p-6 rounded-2xl">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
                <Activity className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-gray-400 text-sm font-medium">Uploaded Today</h3>
                <p className="text-3xl font-bold text-white">{metrics?.processed_today || 0}</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/40 backdrop-blur-md border border-gray-700/50 p-6 rounded-2xl md:col-span-1">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400">
                <CloudUpload className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-gray-400 text-sm font-medium">Auto-Ingestion</h3>
                <p className="text-3xl font-bold text-white">Active</p>
              </div>
            </div>
          </div>
        </section>

        <section className="mb-12">
          <FileUpload onUploadSuccess={fetchData} />
        </section>

        <section>
          <h3 className="text-2xl font-bold mb-6 flex items-center">
            My File History
            <span className="ml-3 px-2 py-1 bg-blue-500/10 text-blue-400 text-xs rounded-full border border-blue-500/20">
              {files.length} Files
            </span>
          </h3>

          <div className="bg-gray-800/30 backdrop-blur-sm border border-gray-700/50 rounded-2xl overflow-hidden shadow-xl">
            {files.length === 0 ? (
              <div className="p-20 text-center text-gray-400">
                <FileText className="w-12 h-12 mx-auto mb-4 text-gray-600 opacity-50" />
                <p className="text-lg">No files uploaded yet.</p>
                <p className="text-sm mt-2">Upload your first data asset above to see it here.</p>
              </div>
            ) : (
              <FileList files={files} onRefresh={fetchData} />
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default UserDashboard;