import React, { useState, useRef, useEffect } from 'react'
import { Lock, Mail, Shield, ArrowRight, Loader2, CheckCircle2, AlertCircle, Smartphone } from 'lucide-react'
import { requestOTP, verifyOTP } from '../services/api'

export default function LoginPage({ onLoginSuccess }) {
  const [step, setStep] = useState('email')   // 'email' | 'otp' | 'success'
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(0)

  const otpRefs = useRef([])

  // Countdown timer for resend
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown(c => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  // Focus first OTP input when step changes to 'otp'
  useEffect(() => {
    if (step === 'otp') {
      setTimeout(() => otpRefs.current[0]?.focus(), 100)
    }
  }, [step])

  async function handleSendOTP(e) {
    e.preventDefault()
    if (!email.trim()) {
      setError('Please enter your email')
      return
    }

    setLoading(true)
    setError('')

    try {
      const result = await requestOTP(email.trim())
      if (result.error) {
        setError(result.error)
      } else {
        setStep('otp')
        setCountdown(300) // 5 minutes
        setOtp(['', '', '', '', '', ''])
      }
    } catch (err) {
      setError(err.message || 'Failed to send OTP')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOTP() {
    const otpString = otp.join('')
    if (otpString.length !== 6) {
      setError('Please enter the complete 6-digit OTP')
      return
    }

    setLoading(true)
    setError('')

    try {
      const result = await verifyOTP(email.trim(), otpString)
      if (result.error) {
        setError(result.error)
        // Clear OTP fields on error
        setOtp(['', '', '', '', '', ''])
        setTimeout(() => otpRefs.current[0]?.focus(), 100)
      } else if (result.token) {
        setStep('success')
        setTimeout(() => onLoginSuccess(result.email), 800)
      }
    } catch (err) {
      setError(err.message || 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  function handleOtpChange(index, value) {
    // Only allow digits
    const digit = value.replace(/\D/g, '').slice(-1)
    const newOtp = [...otp]
    newOtp[index] = digit
    setOtp(newOtp)
    setError('')

    // Auto-focus next input
    if (digit && index < 5) {
      otpRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all 6 digits entered
    if (digit && index === 5) {
      const full = newOtp.join('')
      if (full.length === 6) {
        setTimeout(() => handleVerifyOTP(), 100)
      }
    }
  }

  function handleOtpKeyDown(index, e) {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus()
    }
    if (e.key === 'Enter') {
      handleVerifyOTP()
    }
  }

  function handleOtpPaste(e) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (pasted.length > 0) {
      const newOtp = [...otp]
      for (let i = 0; i < pasted.length; i++) {
        newOtp[i] = pasted[i]
      }
      setOtp(newOtp)
      if (pasted.length === 6) {
        // Auto-submit after paste
        setTimeout(() => {
          const otpString = newOtp.join('')
          if (otpString.length === 6) handleVerifyOTP()
        }, 100)
      } else {
        otpRefs.current[Math.min(pasted.length, 5)]?.focus()
      }
    }
  }

  async function handleResendOTP() {
    if (countdown > 0) return
    setLoading(true)
    setError('')
    try {
      const result = await requestOTP(email.trim())
      if (result.error) {
        setError(result.error)
      } else {
        setCountdown(300)
        setOtp(['', '', '', '', '', ''])
        setTimeout(() => otpRefs.current[0]?.focus(), 100)
      }
    } catch (err) {
      setError(err.message || 'Failed to resend OTP')
    } finally {
      setLoading(false)
    }
  }

  const formatCountdown = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="min-h-screen bg-dark-900 flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-pink-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-pink-500 mb-4">
            <Shield size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-pink-400">Intra</span>
            <span className="text-white">Trading</span>
          </h1>
          <p className="text-gray-500 text-sm mt-1">Secure Portal Access</p>
        </div>

        {/* Card */}
        <div className="bg-dark-800 border border-dark-600 rounded-2xl p-8 shadow-2xl">

          {/* Step 1: Email */}
          {step === 'email' && (
            <form onSubmit={handleSendOTP}>
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-500/10 mb-3">
                  <Mail size={24} className="text-blue-400" />
                </div>
                <h2 className="text-lg font-semibold text-white">Sign In</h2>
                <p className="text-gray-400 text-sm mt-1">Enter your email to receive a one-time password</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Email Address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError('') }}
                    placeholder="your@email.com"
                    autoFocus
                    autoComplete="email"
                    className="w-full bg-dark-700 border border-dark-500 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 transition-colors"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    <AlertCircle size={14} />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-orange-500 to-pink-500 text-white rounded-xl px-4 py-3 font-semibold hover:opacity-90 disabled:opacity-40 transition-opacity"
                >
                  {loading ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <>
                      Send OTP <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>

              <div className="flex items-center gap-2 mt-5 pt-4 border-t border-dark-600">
                <Smartphone size={14} className="text-gray-500" />
                <p className="text-[11px] text-gray-500">OTP will be sent to your Telegram</p>
              </div>
            </form>
          )}

          {/* Step 2: OTP Verification */}
          {step === 'otp' && (
            <div>
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-green-500/10 mb-3">
                  <Lock size={24} className="text-green-400" />
                </div>
                <h2 className="text-lg font-semibold text-white">Enter OTP</h2>
                <p className="text-gray-400 text-sm mt-1">
                  Check your Telegram for the 6-digit code
                </p>
              </div>

              <div className="space-y-4">
                {/* OTP Input Boxes */}
                <div className="flex justify-center gap-3">
                  {otp.map((digit, i) => (
                    <input
                      key={i}
                      ref={el => otpRefs.current[i] = el}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(i, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(i, e)}
                      onPaste={i === 0 ? handleOtpPaste : undefined}
                      className="w-12 h-14 text-center text-xl font-bold bg-dark-700 border border-dark-500 rounded-xl text-white focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 transition-colors"
                    />
                  ))}
                </div>

                {/* Timer */}
                {countdown > 0 && (
                  <p className="text-center text-xs text-gray-500">
                    OTP expires in <span className="text-orange-400 font-mono">{formatCountdown(countdown)}</span>
                  </p>
                )}

                {error && (
                  <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    <AlertCircle size={14} />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  onClick={handleVerifyOTP}
                  disabled={loading || otp.join('').length !== 6}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-orange-500 to-pink-500 text-white rounded-xl px-4 py-3 font-semibold hover:opacity-90 disabled:opacity-40 transition-opacity"
                >
                  {loading ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <>
                      Verify <CheckCircle2 size={16} />
                    </>
                  )}
                </button>

                {/* Resend + Back */}
                <div className="flex items-center justify-between pt-2">
                  <button
                    onClick={() => { setStep('email'); setError(''); setOtp(['', '', '', '', '', '']) }}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    Change email
                  </button>
                  <button
                    onClick={handleResendOTP}
                    disabled={countdown > 0 || loading}
                    className="text-xs text-orange-400 hover:text-orange-300 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
                  >
                    {countdown > 0 ? `Resend in ${formatCountdown(countdown)}` : 'Resend OTP'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Success */}
          {step === 'success' && (
            <div className="text-center py-4">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/10 mb-4">
                <CheckCircle2 size={32} className="text-green-400" />
              </div>
              <h2 className="text-lg font-semibold text-white mb-1">Welcome Back</h2>
              <p className="text-gray-400 text-sm">Authentication successful. Loading dashboard...</p>
              <div className="mt-4">
                <Loader2 size={20} className="animate-spin text-orange-400 mx-auto" />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-gray-600 mt-6">
          Secured with OTP + JWT authentication
        </p>
      </div>
    </div>
  )
}
