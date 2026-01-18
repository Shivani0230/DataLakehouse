// src/components/FileList.jsx
import React from 'react';
import { FileCode, FileText, Image as ImageIcon, Table as TableIcon, File as FileIcon, ExternalLink, Calendar, HardDrive } from 'lucide-react';

const FileList = ({ files }) => {
  const getFileIcon = (format) => {
    switch (format?.toLowerCase()) {
      case 'csv':
      case 'parquet':
        return <TableIcon className="w-5 h-5 text-emerald-400" />;
      case 'json':
        return <FileCode className="w-5 h-5 text-amber-400" />;
      case 'pdf':
        return <FileText className="w-5 h-5 text-red-500" />;
      case 'png':
      case 'jpg':
      case 'jpeg':
        return <ImageIcon className="w-5 h-5 text-purple-400" />;
      default:
        return <FileIcon className="w-5 h-5 text-blue-400" />;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-gray-700/50 bg-gray-900/50">
            <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Asset Name</th>
            <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Size</th>
            <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Format</th>
            <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Created At</th>
            <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/30">
          {files.map((file) => (
            <tr key={file.object_name} className="hover:bg-blue-500/5 transition-colors group">
              <td className="p-4">
                <div className="flex items-center">
                  <div className="mr-3 p-2 bg-gray-800 rounded-lg group-hover:bg-gray-700 transition-colors">
                    {getFileIcon(file.file_format)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white truncate max-w-xs" title={file.object_name}>
                      {file.object_name.split('/').pop()}
                    </p>
                    <p className="text-xs text-gray-500 truncate">{file.object_name}</p>
                  </div>
                </div>
              </td>
              <td className="p-4">
                <div className="flex items-center text-sm text-gray-300">
                  <HardDrive className="w-3.5 h-3.5 mr-1.5 text-gray-500" />
                  {formatSize(file.object_size)}
                </div>
              </td>
              <td className="p-4">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gray-700 text-gray-300 border border-gray-600">
                  {file.file_format || 'Unknown'}
                </span>
              </td>
              <td className="p-4">
                <div className="flex items-center text-xs text-gray-400">
                  <Calendar className="w-3.5 h-3.5 mr-1.5 text-gray-600" />
                  {formatDate(file.created_at)}
                </div>
              </td>
              <td className="p-4 text-right">
                <button
                  className="p-2 text-gray-400 hover:text-blue-400 hover:bg-blue-400/10 rounded-lg transition-all"
                  title="View Details"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default FileList;