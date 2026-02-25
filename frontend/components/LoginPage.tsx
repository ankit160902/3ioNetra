/**
 * Login/Register Page Component with Extended Profile Collection
 */
import { useState } from 'react';
import { Loader2, Eye, EyeOff, ChevronRight, ChevronLeft } from 'lucide-react';

export interface UserProfile {
  name: string;
  email: string;
  password: string;
  phone: string;
  gender: string;
  dob: string;
  profession: string;
}

interface LoginPageProps {
  onLogin: (email: string, password: string) => Promise<boolean>;
  onRegister: (profile: UserProfile) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
}

const professionOptions = [
  { value: 'student', label: 'Student' },
  { value: 'professional', label: 'Working Professional' },
  { value: 'business', label: 'Business Owner / Entrepreneur' },
  { value: 'homemaker', label: 'Homemaker' },
  { value: 'retired', label: 'Retired' },
  { value: 'caregiver', label: 'Caregiver' },
  { value: 'other', label: 'Other' },
];

const genderOptions = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'other', label: 'Other' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

export default function LoginPage({ onLogin, onRegister, isLoading, error }: LoginPageProps) {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [registrationStep, setRegistrationStep] = useState(1); // 1: basic info, 2: profile details

  // Basic info
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Profile details
  const [phone, setPhone] = useState('');
  const [gender, setGender] = useState('');
  const [dob, setDob] = useState('');
  const [profession, setProfession] = useState('');

  const [localError, setLocalError] = useState<string | null>(null);

  const validateStep1 = (): boolean => {
    if (!name.trim()) {
      setLocalError('Please enter your name');
      return false;
    }
    if (!email.trim() || !email.includes('@')) {
      setLocalError('Please enter a valid email address');
      return false;
    }
    if (password.length < 6) {
      setLocalError('Password must be at least 6 characters');
      return false;
    }
    if (password !== confirmPassword) {
      setLocalError('Passwords do not match');
      return false;
    }
    return true;
  };

  const validateStep2 = (): boolean => {
    if (!phone.trim() || phone.length < 10) {
      setLocalError('Please enter a valid phone number');
      return false;
    }
    if (!gender) {
      setLocalError('Please select your gender');
      return false;
    }
    if (!dob) {
      setLocalError('Please enter your date of birth');
      return false;
    }
    if (!profession) {
      setLocalError('Please select your profession');
      return false;
    }
    return true;
  };

  const handleNextStep = () => {
    setLocalError(null);
    if (validateStep1()) {
      setRegistrationStep(2);
    }
  };

  const handlePrevStep = () => {
    setLocalError(null);
    setRegistrationStep(1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (isRegisterMode) {
      if (registrationStep === 1) {
        handleNextStep();
        return;
      }

      // Step 2 - Final registration
      if (!validateStep2()) {
        return;
      }

      await onRegister({
        name,
        email,
        password,
        phone,
        gender,
        dob,
        profession,
      });
    } else {
      await onLogin(email, password);
    }
  };

  const switchMode = () => {
    setIsRegisterMode(!isRegisterMode);
    setRegistrationStep(1);
    setLocalError(null);
    setName('');
    setEmail('');
    setPassword('');
    setConfirmPassword('');
    setPhone('');
    setGender('');
    setDob('');
    setProfession('');
  };

  // Calculate max date for DOB (user should be at least 13 years old)
  const today = new Date();
  const maxDate = new Date(today.getFullYear() - 13, today.getMonth(), today.getDate())
    .toISOString().split('T')[0];
  const minDate = new Date(today.getFullYear() - 100, today.getMonth(), today.getDate())
    .toISOString().split('T')[0];

  return (
    <div className="min-h-[100dvh] bg-gradient-to-br from-orange-50/50 via-white to-amber-50/50 flex items-center justify-center p-6 font-['Inter']">
      <div className="w-full max-w-[400px] animate-fade-in">
        {/* Logo Text */}
        <div className="text-center mb-8 flex flex-col items-center">
          <img src="/logo-full.png" alt="3ioNetra" className="h-20 object-contain mb-2" />
          <p className="text-[11px] font-black uppercase tracking-[0.3em] text-orange-600">Elevate Your Spirit</p>
        </div>

        {/* Login/Register Form */}
        <div className="bg-white/80 backdrop-blur-xl rounded-[2rem] shadow-2xl shadow-orange-900/5 p-7 md:p-8 border border-orange-100/50">
          <h2 className="text-base font-black text-gray-900 mb-6 text-center uppercase tracking-widest opacity-80">
            {isRegisterMode
              ? (registrationStep === 1 ? 'Create Account' : 'Complete Profile')
              : 'Welcome Back'}
          </h2>

          {/* Progress indicator for registration */}
          {isRegisterMode && (
            <div className="flex items-center justify-center gap-2 mb-6">
              <div className={`w-2 h-2 rounded-full transition-all duration-500 ${registrationStep >= 1 ? 'bg-orange-500 w-4' : 'bg-gray-200'}`} />
              <div className={`w-2 h-2 rounded-full transition-all duration-500 ${registrationStep >= 2 ? 'bg-orange-500 w-4' : 'bg-gray-200'}`} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Step 1: Basic Info */}
            {(!isRegisterMode || registrationStep === 1) && (
              <>
                {isRegisterMode && (
                  <div>
                    <label htmlFor="name" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                      Full Name
                    </label>
                    <input
                      id="name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your Name"
                      required={isRegisterMode}
                      className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none"
                    />
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@nexus.com"
                    required
                    className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none pr-14"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-orange-600 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {isRegisterMode && (
                  <div>
                    <label htmlFor="confirmPassword" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                      Confirm
                    </label>
                    <input
                      id="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      required={isRegisterMode}
                      className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none"
                    />
                  </div>
                )}
              </>
            )}

            {/* Step 2: Profile Details */}
            {isRegisterMode && registrationStep === 2 && (
              <>
                <div>
                  <label htmlFor="phone" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Phone
                  </label>
                  <input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 15))}
                    placeholder="Your Phone Number"
                    required
                    className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none"
                  />
                </div>

                <div>
                  <label htmlFor="gender" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Gender
                  </label>
                  <select
                    id="gender"
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    required
                    className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none appearance-none cursor-pointer"
                  >
                    <option value="">Select Gender</option>
                    {genderOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="dob" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Date of Birth
                  </label>
                  <input
                    id="dob"
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    max={maxDate}
                    min={minDate}
                    required
                    className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none cursor-pointer"
                  />
                </div>

                <div>
                  <label htmlFor="profession" className="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5 ml-1">
                    Profession
                  </label>
                  <select
                    id="profession"
                    value={profession}
                    onChange={(e) => setProfession(e.target.value)}
                    required
                    className="w-full px-5 py-3.5 bg-gray-50/50 border border-orange-100 rounded-2xl focus:ring-4 focus:ring-orange-500/5 focus:border-orange-200 focus:bg-white text-sm font-bold transition-all outline-none appearance-none cursor-pointer"
                  >
                    <option value="">Select Profession</option>
                    {professionOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {/* Error Display */}
            {(error || localError) && (
              <div className="bg-red-50/50 border border-red-100 rounded-2xl p-4 animate-fade-in">
                <p className="text-[11px] font-black uppercase tracking-tighter text-red-600 text-center">{localError || error}</p>
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-3 pt-4">
              {isRegisterMode && registrationStep === 2 && (
                <button
                  type="button"
                  onClick={handlePrevStep}
                  className="flex-1 py-4 bg-white border border-orange-100 text-orange-600 font-black uppercase tracking-widest text-[10px] rounded-2xl hover:bg-orange-50 transition-all active:scale-95 shadow-sm"
                >
                  Back
                </button>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="flex-[2] py-4 bg-gradient-to-br from-orange-500 to-amber-600 text-white font-black uppercase tracking-[0.2em] text-[10px] rounded-2xl hover:from-orange-600 hover:to-amber-700 transition-all disabled:opacity-50 disabled:grayscale shadow-lg shadow-orange-900/10 active:scale-95 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : isRegisterMode ? (
                  registrationStep === 1 ? 'Next Step' : 'Create Account'
                ) : (
                  'Sign In'
                )}
              </button>
            </div>
          </form>

          <div className="mt-8 text-center">
            <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">
              {isRegisterMode ? 'Already a member?' : "New here?"}
              <button
                onClick={switchMode}
                className="ml-2 text-orange-600 hover:text-orange-700 transition-colors underline underline-offset-4"
              >
                {isRegisterMode ? 'Sign In' : 'Create Account'}
              </button>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[9px] font-black uppercase tracking-[0.3em] text-gray-300 mt-10 opacity-60">
          Nexus of Ancient Wisdom & Modern Soul
        </p>
      </div>
    </div>
  );
}