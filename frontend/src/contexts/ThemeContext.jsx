import React, { createContext, useContext, useState, useEffect } from 'react'

const STORAGE_KEY = 'intratrading-theme'
const VALID_THEMES = ['dark', 'light', 'midnight']
const DEFAULT_THEME = 'dark'

const ThemeContext = createContext({
  theme: DEFAULT_THEME,
  setTheme: () => {},
})

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored && VALID_THEMES.includes(stored)) return stored
    } catch {}
    return DEFAULT_THEME
  })

  function setTheme(newTheme) {
    if (!VALID_THEMES.includes(newTheme)) return
    setThemeState(newTheme)
    try {
      localStorage.setItem(STORAGE_KEY, newTheme)
    } catch {}
  }

  // Apply data-theme attribute to body whenever theme changes
  useEffect(() => {
    document.body.setAttribute('data-theme', theme)
    // Also set on <html> for full coverage
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}

export default ThemeContext
