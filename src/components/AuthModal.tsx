import React, { useState } from 'react';
import { ShieldCheck, X, Check, Lock, Building, ArrowRight } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentRole: string;
  onRoleChange: (role: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  currentRole,
  onRoleChange,
}) => {
  const [selectedRole, setSelectedRole] = useState(currentRole);
  const [email, setEmail] = useState('preeti.s@enterprise.corp');
  const [password, setPassword] = useState('••••••••••••');
  const [ssoProvider, setSsoProvider] = useState<string | null>(null);

  if (!isOpen) return null;

  const roles = [
    {
      id: 'Lead Finance Auditor',
      title: 'Finance Auditor',
      desc: 'Full approval, rejection with clause citation, duplicate review, and audit trail export.',
    },
    {
      id: 'HR & People Operations',
      title: 'HR Admin',
      desc: 'Employee compliance health scores, submission SLA latencies, and policy exceptions.',
    },
    {
      id: 'Engineering Manager',
      title: 'Manager Approver',
      desc: 'First-line department budget oversight, team claims, and SLA notifications.',
    },
  ];

  const handleApply = () => {
    onRoleChange(selectedRole);
    onClose();
  };

  const handleSSOLogin = (provider: string) => {
    setSsoProvider(provider);
    setTimeout(() => {
      onRoleChange(selectedRole);
      setSsoProvider(null);
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-md bg-white rounded-lg border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-slate-900 text-white font-bold text-xs">
              PL
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Proofline Enterprise Sign-In</h2>
              <p className="text-[11px] text-slate-500">Corporate Single Sign-On & Role Delegation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* SSO Buttons */}
          <div className="space-y-2">
            <button
              onClick={() => handleSSOLogin('Google Workspace')}
              disabled={!!ssoProvider}
              className="w-full flex items-center justify-center gap-2.5 h-9 px-3 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>{ssoProvider === 'Google Workspace' ? 'Authenticating with Google...' : 'Sign in with Google Workspace'}</span>
            </button>

            <button
              onClick={() => handleSSOLogin('Okta')}
              disabled={!!ssoProvider}
              className="w-full flex items-center justify-center gap-2.5 h-9 px-3 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              <div className="h-4 w-4 rounded-full border-2 border-[#007DC1] flex items-center justify-center">
                <div className="h-1.5 w-1.5 rounded-full bg-[#007DC1]" />
              </div>
              <span>{ssoProvider === 'Okta' ? 'Verifying Okta SAML...' : 'Sign in with Okta SSO'}</span>
            </button>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="border-t border-slate-200 w-full" />
            <span className="bg-white px-2 text-[11px] text-slate-400 absolute">or manual credentials</span>
          </div>

          {/* Form Fields */}
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-600 mb-1">
                Corporate Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-8 px-2.5 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-600 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-8 px-2.5 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
              />
            </div>
          </div>

          {/* Role Delegation */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Delegate Active Role
            </label>
            <div className="space-y-1.5">
              {roles.map((r) => {
                const isSelected = selectedRole === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedRole(r.id)}
                    className={`cursor-pointer p-2.5 rounded border transition-colors ${
                      isSelected
                        ? 'border-slate-900 bg-slate-50'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className={`h-3.5 w-3.5 rounded-full border flex items-center justify-center ${
                            isSelected
                              ? 'border-slate-900 bg-slate-900'
                              : 'border-slate-300'
                          }`}
                        >
                          {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
                        </div>
                        <span className="text-xs font-semibold text-slate-900">
                          {r.title}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {r.id.split(' ')[0]}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1 pl-5.5">
                      {r.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 bg-slate-50 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <Lock className="h-3 w-3 text-slate-400" />
            <span>SOC-2 Type II · 256-bit TLS</span>
          </div>
          <button
            onClick={handleApply}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors shadow-xs"
          >
            <span>Confirm & Enter</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
