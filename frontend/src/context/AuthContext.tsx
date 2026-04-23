import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { auth } from '../firebase';
import { onAuthStateChanged, signOut, User as FirebaseUser } from 'firebase/auth';
import { resolveApiBaseUrl } from '../utils/apiBaseUrl';

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
    authError: string;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [authError, setAuthError] = useState('');

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
                    setAuthError('');
                } catch (err) {
                    console.error("Failed to sync user with backend", err);
                    if (axios.isAxiosError(err) && err.response?.status === 401) {
                        setAuthError('Your sign-in succeeded, but this account is not provisioned for the Partner Console yet. Ask an administrator to create or activate your backend user profile.');
                    } else if (axios.isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
                        setAuthError(err.response.data.detail);
                    } else {
                        setAuthError('We could not sync your account with the backend. Please try again in a moment.');
                    }
                    setUser(null);
                }
            } else {
                setUser(null);
                setAuthError('');
            }
            setIsLoading(false);
        });

        return () => unsubscribe();
    }, []);

    const logout = async () => {
        await signOut(auth);
        setUser(null);
        setAuthError('');
    };

    return (
        <AuthContext.Provider value={{ user, logout, isLoading, authError }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
export { api };
