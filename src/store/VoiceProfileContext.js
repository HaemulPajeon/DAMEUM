import { createContext, useContext, useState } from 'react';

const VoiceProfileContext = createContext(null);

export function VoiceProfileProvider({ children }) {
    const [profile, setProfileState] = useState({
        name: '00님의 목소리',
        date: '2026.07.15',
        duration: '3:30',
    });

    const setProfile = ({ name, duration }) => {
        const today = new Date();
        const dateStr = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`;
        setProfileState({
            name: name || '00님의 목소리',
            date: dateStr,
            duration: duration || '0:00',
        });
    };

    return (
        <VoiceProfileContext.Provider value={{ profile, setProfile }}>
            {children}
        </VoiceProfileContext.Provider>
    );
}

export function useVoiceProfile() {
    const ctx = useContext(VoiceProfileContext);
    if (!ctx) throw new Error('useVoiceProfile must be used within VoiceProfileProvider');
    return ctx;
}