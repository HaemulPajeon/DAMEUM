import { createContext, useCallback, useContext, useState } from 'react';

const RecentItemsContext = createContext(null);

export function RecentItemsProvider({ children }) {
  const [items, setItems] = useState([]);

  const addItem = useCallback((item) => {
    setItems((prev) => [
      { ...item, id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, timestamp: Date.now() },
      ...prev,
    ].slice(0, 10));
  }, []);

  return (
    <RecentItemsContext.Provider value={{ items, addItem }}>
      {children}
    </RecentItemsContext.Provider>
  );
}

export function useRecentItems() {
  const ctx = useContext(RecentItemsContext);
  if (!ctx) {
    throw new Error('useRecentItems must be used within a RecentItemsProvider');
  }
  return ctx;
}
