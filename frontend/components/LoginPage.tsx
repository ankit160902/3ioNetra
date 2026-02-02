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
  rashi?: string;
  gotra?: string;
  nakshatra?: string;
  preferred_deity?: string;
  temple_visits?: string[];
  purchase_history?: string[];
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
  const [rashi, setRashi] = useState('');
  const [gotra, setGotra] = useState('');
  const [nakshatra, setNakshatra] = useState('');
  const [preferredDeity, setPreferredDeity] = useState('');
  const [templeVisits, setTempleVisits] = useState('');
  const [purchaseHistory, setPurchaseHistory] = useState('');

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
        rashi,
        gotra,
        nakshatra,
        preferred_deity: preferredDeity,
        temple_visits: templeVisits ? templeVisits.split(',').map(s => s.trim()) : [],
        purchase_history: purchaseHistory ? purchaseHistory.split(',').map(s => s.trim()) : [],
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
    setRashi('');
    setGotra('');
    setNakshatra('');
    setPreferredDeity('');
    setTempleVisits('');
    setPurchaseHistory('');
  };

  // Calculate max date for DOB (user should be at least 13 years old)
  const today = new Date();
  const maxDate = new Date(today.getFullYear() - 13, today.getMonth(), today.getDate())
    .toISOString().split('T')[0];
  const minDate = new Date(today.getFullYear() - 100, today.getMonth(), today.getDate())
    .toISOString().split('T')[0];

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-amber-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo Text */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">3ioNetra</h1>
          <p className="text-lg text-orange-600 mt-1">Spiritual Companion</p>
        </div>

        {/* Login/Register Form */}
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-orange-100">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 text-center">
            {isRegisterMode
              ? (registrationStep === 1 ? 'Create Your Account' : 'Complete Your Profile')
              : 'Welcome Back'}
          </h2>

          {/* Progress indicator for registration */}
          {isRegisterMode && (
            <div className="flex items-center justify-center gap-2 mb-4">
              <div className={`w-3 h-3 rounded-full ${registrationStep >= 1 ? 'bg-orange-500' : 'bg-gray-300'}`} />
              <div className={`w-8 h-0.5 ${registrationStep >= 2 ? 'bg-orange-500' : 'bg-gray-300'}`} />
              <div className={`w-3 h-3 rounded-full ${registrationStep >= 2 ? 'bg-orange-500' : 'bg-gray-300'}`} />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            {/* Step 1: Basic Info */}
            {(!isRegisterMode || registrationStep === 1) && (
              <>
                {isRegisterMode && (
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                      Full Name
                    </label>
                    <input
                      id="name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Enter your full name"
                      required={isRegisterMode}
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      required
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors pr-12"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {isRegisterMode && (
                  <div>
                    <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                      Confirm Password
                    </label>
                    <input
                      id="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm your password"
                      required={isRegisterMode}
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>
                )}
              </>
            )}

            {/* Step 2: Profile Details */}
            {isRegisterMode && registrationStep === 2 && (
              <>
                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 15))}
                    placeholder="Enter your phone number"
                    required
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="gender" className="block text-sm font-medium text-gray-700 mb-1">
                    Gender
                  </label>
                  <select
                    id="gender"
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors bg-white"
                  >
                    <option value="">Select your gender</option>
                    {genderOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="dob" className="block text-sm font-medium text-gray-700 mb-1">
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
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="profession" className="block text-sm font-medium text-gray-700 mb-1">
                    Profession
                  </label>
                  <select
                    id="profession"
                    value={profession}
                    onChange={(e) => setProfession(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors bg-white"
                  >
                    <option value="">Select your profession</option>
                    {professionOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="rashi" className="block text-sm font-medium text-gray-700 mb-1">
                      Rashi
                    </label>
                    <input
                      id="rashi"
                      type="text"
                      value={rashi}
                      onChange={(e) => setRashi(e.target.value)}
                      placeholder="e.g. Mesha"
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>

                  <div>
                    <label htmlFor="nakshatra" className="block text-sm font-medium text-gray-700 mb-1">
                      Nakshatra
                    </label>
                    <input
                      id="nakshatra"
                      type="text"
                      value={nakshatra}
                      onChange={(e) => setNakshatra(e.target.value)}
                      placeholder="e.g. Ashwini"
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="gotra" className="block text-sm font-medium text-gray-700 mb-1">
                      Gotra
                    </label>
                    <input
                      id="gotra"
                      type="text"
                      value={gotra}
                      onChange={(e) => setGotra(e.target.value)}
                      placeholder="e.g. Kashyapa"
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>

                  <div>
                    <label htmlFor="preferred_deity" className="block text-sm font-medium text-gray-700 mb-1">
                      Preferred Deity (Ishta Devata)
                    </label>
                    <input
                      id="preferred_deity"
                      type="text"
                      value={preferredDeity}
                      onChange={(e) => setPreferredDeity(e.target.value)}
                      placeholder="e.g. Shiva, Krishna"
                      className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="temple_visits" className="block text-sm font-medium text-gray-700 mb-1">
                    Previous Temple Visits (if any)
                  </label>
                  <input
                    id="temple_visits"
                    type="text"
                    value={templeVisits}
                    onChange={(e) => setTempleVisits(e.target.value)}
                    placeholder="e.g. Kashi Vishwanath, Tirupati (separate by comma)"
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="purchase_history" className="block text-sm font-medium text-gray-700 mb-1">
                    Previous Spiritual Purchases (if any)
                  </label>
                  <input
                    id="purchase_history"
                    type="text"
                    value={purchaseHistory}
                    onChange={(e) => setPurchaseHistory(e.target.value)}
                    placeholder="e.g. Rudraksha Mala, Geeta (separate by comma)"
                    className="w-full px-4 py-2.5 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-colors"
                  />
                </div>

                <p className="text-xs text-gray-500 text-center">
                  This information helps us provide personalized spiritual guidance
                </p>
              </>
            )}

            {/* Error Display */}
            {(error || localError) && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm text-red-600">{localError || error}</p>
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-2 pt-2">
              {isRegisterMode && registrationStep === 2 && (
                <button
                  type="button"
                  onClick={handlePrevStep}
                  className="flex-1 py-2.5 border border-orange-300 text-orange-600 font-medium rounded-lg hover:bg-orange-50 transition-colors flex items-center justify-center gap-1"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Back
                </button>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 text-white font-semibold rounded-lg hover:from-orange-600 hover:to-amber-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md flex items-center justify-center gap-1"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    {isRegisterMode ? 'Creating...' : 'Signing in...'}
                  </span>
                ) : isRegisterMode ? (
                  registrationStep === 1 ? (
                    <>
                      Next
                      <ChevronRight className="w-4 h-4" />
                    </>
                  ) : (
                    'Create Account'
                  )
                ) : (
                  'Sign In'
                )}
              </button>
            </div>
          </form>

          <div className="mt-4 text-center">
            <p className="text-sm text-gray-600">
              {isRegisterMode ? 'Already have an account?' : "Don't have an account?"}
              <button
                onClick={switchMode}
                className="ml-1 text-orange-600 hover:text-orange-700 font-medium underline"
              >
                {isRegisterMode ? 'Sign In' : 'Create one'}
              </button>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-500 mt-4">
          By using 3ioNetra, you agree to seek wisdom with an open heart
        </p>
      </div>
    </div>
  );
}