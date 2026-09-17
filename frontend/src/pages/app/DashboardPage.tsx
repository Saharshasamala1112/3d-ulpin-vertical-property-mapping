import { useAuth } from '../../app/AuthContext';
import { PageContainer } from '../../components/layout/PageContainer';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';

export function DashboardPage() {
  const { user } = useAuth();

  const modules = [
    { name: 'Parcels', description: 'Manage land parcels and ULPINs', status: 'available' as const },
    { name: 'Buildings', description: 'Building hierarchy management', status: 'available' as const },
    { name: 'Units', description: 'Floor and unit management', status: 'available' as const },
    { name: 'VDC', description: 'Vertical DNA Code engine', status: 'coming-soon' as const },
    { name: 'Validation', description: '3D topology validation', status: 'coming-soon' as const },
    { name: 'Ownership', description: 'Property governance', status: 'coming-soon' as const },
    { name: '3D Visualization', description: 'Volumetric property views', status: 'coming-soon' as const },
  ];

  return (
    <PageContainer
      title="Dashboard"
      description={`Welcome back, ${user?.full_name || 'User'}`}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '1rem',
        }}
      >
        {modules.map((mod) => (
          <Card key={mod.name} padding="1.25rem">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>{mod.name}</h3>
              <Badge variant={mod.status === 'available' ? 'success' : 'default'}>
                {mod.status === 'available' ? 'Available' : 'Coming Soon'}
              </Badge>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>{mod.description}</p>
          </Card>
        ))}
      </div>
    </PageContainer>
  );
}
