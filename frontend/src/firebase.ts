import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
    apiKey: "AIzaSyCx9y9fJoku4mNPTMa6otsav1uyJOZT4oE",
    authDomain: "mfi--pro.firebaseapp.com",
    projectId: "mfi--pro",
    storageBucket: "mfi--pro.firebasestorage.app",
    messagingSenderId: "139601123738",
    appId: "1:139601123738:web:9d23cc2ffd0d99e2d18223",
    measurementId: "G-YLBQHF9XBE"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const analytics = typeof window !== 'undefined' ? getAnalytics(app) : null;
export default app;
