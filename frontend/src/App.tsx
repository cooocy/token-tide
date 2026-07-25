import { Navigate, Route, Routes } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';
import ProviderHistoryPage from '@/pages/ProviderHistoryPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/providers/:provider/history" element={<ProviderHistoryPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
