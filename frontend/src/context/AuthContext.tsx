import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { auth } from '../firebase';
import { onAuthStateChanged, signOut, User as FirebaseUser } from 'firebase/auth';

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);

const resolveApiBaseUrl = () => {
    const configuredBaseUrl = import.meta.env.VITE_API_URL?.trim();
    if (typeof window !== 'undefined' && LOCAL_HOSTS.has(window.location.hostname)) {
        if (!configuredBaseUrl || configuredBaseUrl === '/api') {
            return 'http://localhost:8000';
        }
    }
    return configuredBaseUrl || 'http://localhost:8000';
};

// Configure Axios
const api = axios.create({
    baseURL: resolveApiBaseUrl(),
});

// Add token to requests
api.interceptors.request.use(async (config) => {
    const user = auth.currentUser;
    if (user) {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

interface AuthContextType {
    user: any;
    isLoading: boolean;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            if (firebaseUser) {
                try {
                    // Sync with backend to get organization/role data
                    const token = await firebaseUser.getIdToken();
                    const res = await axios.get(`${api.defaults.baseURL}/auth/me`, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    setUser(res.data);
                } catch (err) {
                    console.error("Failed to sync user with backend", err);
                    setUser(null);
                }
            } else {
                setUser(null);
            }
            setIsLoading(false);
        });

        return () => unsubscribe();
    }, []);

    const logout = async () => {
        await signOut(auth);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
export { api };
