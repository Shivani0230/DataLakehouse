// src/pages/AdminDashboard.jsx
import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import FileList from '../components/FileList';
import FileUpload from '../components/FileUpload';
import UserManager from '../components/UserManager';
import { dashboardAPI } from '../services/api';
import { Database, Activity, HardDrive, BarChart3, RefreshCw } from 'lucide-react';

const AdminDashboard = () => {
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
      <div className="flex flex-col items-center">
        <RefreshCw className="w-10 h-10 text-blue-500 animate-spin mb-4" />
        <p className="text-gray-400 font-medium animate-pulse">Initializing Lakehouse...</p>
      </div>
    </div>
  );

  const StatCard = ({ title, value, icon: Icon, color }) => (
    <div className="bg-gray-800/40 backdrop-blur-md border border-gray-700/50 p-6 rounded-2xl transition-all hover:border-gray-600 group">
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-xl bg-${color}-500/10 text-${color}-400 group-hover:scale-110 transition-transform`}>
          <Icon className="w-6 h-6" />
        </div>
        <BarChart3 className="w-4 h-4 text-gray-600" />
      </div>
      <h3 className="text-gray-400 text-sm font-medium">{title}</h3>
      <p className="text-3xl font-bold mt-1 text-white">{value}</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0f172a] text-white selection:bg-blue-500/30">
      <Navbar />

      <main className="max-w-7xl mx-auto p-8">
        <header className="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-4">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              Admin Control Center
            </h2>
            <p className="text-gray-400 mt-2">Oversee your enterprise data lakehouse operations</p>
          </div>
          <button
            onClick={fetchData}
            disabled={refreshing}
            className="flex items-center px-5 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl transition-all font-medium disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Sync Data
          </button>
        </header>

        {/* Dynamic Metrics Section */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <StatCard
            title="Data Assets"
            value={metrics?.total_documents || 0}
            icon={Database}
            color="blue"
          />
          <StatCard
            title="Processed Today"
            value={metrics?.processed_today || 0}
            icon={Activity}
            color="emerald"
          />
          <StatCard
            title="Storage Used"
            value={`${metrics?.total_storage_gb || 0} GB`}
            icon={HardDrive}
            color="indigo"
          />
          <StatCard
            title="Files in Raw"
            value={metrics?.files_in_raw || 0}
            icon={BarChart3}
            color="amber"
          />
        </section>

        {/* Upload Provision */}
        <section className="mb-12">
          <FileUpload onUploadSuccess={fetchData} />
        </section>

        {/* User Management */}
        <section className="mb-12">
          <UserManager />
        </section>

        {/* Data Catalog Section */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-bold flex items-center">
              Global Data Catalog
              <span className="ml-3 px-2 py-1 bg-blue-500/10 text-blue-400 text-xs rounded-full border border-blue-500/20">
                {files.length} Total
              </span>
            </h3>
          </div>

          <div className="bg-gray-800/30 backdrop-blur-sm border border-gray-700/50 rounded-2xl overflow-hidden shadow-xl">
            {files.length === 0 ? (
              <div className="p-20 text-center">
                <div className="inline-flex p-4 bg-gray-900/50 rounded-full mb-4">
                  <Database className="w-8 h-8 text-gray-600" />
                </div>
                <p className="text-gray-400 text-lg">No assets found in the lakehouse.</p>
                <button onClick={() => fetchData()} className="mt-4 text-blue-400 hover:text-blue-300 font-medium">Try refreshing</button>
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

export default AdminDashboard;