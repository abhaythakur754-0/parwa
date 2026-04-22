'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface JarvisContextType {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

const JarvisContext = createContext<JarvisContextType>({
  isOpen: false,
  open: () => {},
  close: () => {},
});

export function JarvisProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <JarvisContext.Provider
      value={{
        isOpen,
        open: useCallback(() => setIsOpen(true), []),
        close: useCallback(() => setIsOpen(false), []),
      }}
    >
      {children}
    </JarvisContext.Provider>
  );
}

export function useJarvisSidebar() {
  return useContext(JarvisContext);
}
