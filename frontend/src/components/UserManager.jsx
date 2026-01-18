// src/components/UserManager.jsx
import React, { useState, useEffect } from 'react';
import { UserPlus, Trash2, Shield, User, Mail, ShieldCheck, Loader2, X, Plus } from 'lucide-react';
import { dashboardAPI } from '../services/api';

const UserManager = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAddForm, setShowAddForm] = useState(false);
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [actionLoading, setActionLoading] = useState(false);

    const fetchUsers = async () => {
        try {
            const res = await dashboardAPI.getUsers();
            setUsers(res.data);
        } catch (err) {
            console.error('Failed to fetch users', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleAddUser = async (e) => {
        e.preventDefault();
        setActionLoading(true);
        setError('');
        setSuccess('');
        try {
            await dashboardAPI.addUser(newUser);
            setSuccess(`User ${newUser.username} created successfully!`);
            setNewUser({ username: '', password: '', role: 'user' });
            setShowAddForm(false);
            fetchUsers();
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to create user');
        } finally {
            setActionLoading(false);
        }
    };

    const handleDeleteUser = async (id, username) => {
        if (!window.confirm(`Are you sure you want to delete user "${username}"?`)) return;

        setActionLoading(true);
        try {
            await dashboardAPI.deleteUser(id);
            setSuccess(`User ${username} deleted.`);
            fetchUsers();
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to delete user');
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) return (
        <div className="flex justify-center p-12">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
    );

    return (
        <div className="bg-gray-800/40 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-gray-700/50 flex justify-between items-center bg-gray-900/40">
                <div>
                    <h3 className="text-xl font-bold text-white flex items-center">
                        <ShieldCheck className="w-5 h-5 mr-2 text-blue-400" />
                        Identity Management
                    </h3>
                    <p className="text-sm text-gray-500">Manage system access and roles</p>
                </div>
                <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className={`flex items-center px-4 py-2 rounded-xl text-sm font-bold transition-all
            ${showAddForm ? 'bg-gray-700 text-gray-300' : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20'}`}
                >
                    {showAddForm ? <X className="w-4 h-4 mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                    {showAddForm ? 'Cancel' : 'Add User'}
                </button>
            </div>

            {showAddForm && (
                <div className="p-6 bg-blue-500/5 border-b border-gray-700/50 animate-in fade-in slide-in-from-top-4 duration-300">
                    <form onSubmit={handleAddUser} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                        <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Username</label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                                <input
                                    type="text"
                                    required
                                    placeholder="john_doe"
                                    className="w-full bg-gray-900 border border-gray-700 rounded-xl py-2.5 pl-10 pr-4 text-white text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    value={newUser.username}
                                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Password</label>
                            <input
                                type="password"
                                required
                                placeholder="••••••••"
                                className="w-full bg-gray-900 border border-gray-700 rounded-xl py-2.5 px-4 text-white text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                value={newUser.password}
                                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-2">System Role</label>
                            <select
                                className="w-full bg-gray-900 border border-gray-700 rounded-xl py-2.5 px-4 text-white text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all appearance-none"
                                value={newUser.role}
                                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                            >
                                <option value="user">Standard User</option>
                                <option value="admin">Administrator</option>
                            </select>
                        </div>
                        <button
                            type="submit"
                            disabled={actionLoading}
                            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-xl text-sm transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
                        >
                            {actionLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Provision User'}
                        </button>
                    </form>
                    {error && <p className="mt-4 text-sm text-red-400 bg-red-400/10 p-2 rounded-lg border border-red-400/20">{error}</p>}
                </div>
            )}

            {success && (
                <div className="mx-6 mt-6 p-3 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-xl text-sm font-medium animate-in fade-in">
                    {success}
                </div>
            )}

            <div className="p-6">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-xs font-bold text-gray-500 uppercase tracking-wider border-b border-gray-700/50">
                                <th className="pb-4 px-2">Identity</th>
                                <th className="pb-4 px-2">Access Level</th>
                                <th className="pb-4 px-2 text-right">Operations</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-700/30">
                            {users.map((user) => (
                                <tr key={user.id} className="group hover:bg-white/5 transition-colors">
                                    <td className="py-4 px-2">
                                        <div className="flex items-center">
                                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center mr-3 border border-gray-600">
                                                <User className="w-4 h-4 text-gray-400" />
                                            </div>
                                            <span className="text-white font-medium">{user.username}</span>
                                        </div>
                                    </td>
                                    <td className="py-4 px-2">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border
                      ${user.role === 'admin'
                                                ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                                                : 'bg-gray-700/50 text-gray-400 border-gray-600'}`}>
                                            {user.role === 'admin' ? <Shield className="w-3 h-3 mr-1" /> : null}
                                            {user.role}
                                        </span>
                                    </td>
                                    <td className="py-4 px-2 text-right">
                                        {user.username !== 'admin' && (
                                            <button
                                                onClick={() => handleDeleteUser(user.id, user.username)}
                                                className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default UserManager;
