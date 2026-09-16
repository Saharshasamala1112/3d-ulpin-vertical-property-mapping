import { PageContainer } from '../../components/layout/PageContainer';
import { EmptyState } from '../../components/feedback/EmptyState';

interface ModulePageProps {
  title: string;
  description: string;
  icon: string;
}

export function ModulePage({ title, description, icon }: ModulePageProps) {
  return (
    <PageContainer title={title} description={description}>
      <EmptyState
        icon={icon}
        title="Module not available yet"
        description={`${title} management will be implemented in a future sprint.`}
      />
    </PageContainer>
  );
}

export const ParcelsPage = () => (
  <ModulePage title="Parcels" description="Manage land parcels and ULPINs" icon="▭" />
);
export const BuildingsPage = () => (
  <ModulePage title="Buildings" description="Building hierarchy management" icon="⬜" />
);
export const FloorsPage = () => (
  <ModulePage title="Floors" description="Floor hierarchy management" icon="▤" />
);
export const UnitsPage = () => (
  <ModulePage title="Units" description="Floor and unit management" icon="▫" />
);
export const VdcPage = () => (
  <ModulePage title="VDC" description="Vertical DNA Code generation and validation" icon="⊞" />
);
export const TopologyPage = () => (
  <ModulePage title="Topology" description="3D cadastral topology validation" icon="⊡" />
);
export const ValidationPage = () => (
  <ModulePage title="Validation" description="3D cadastral topology validation" icon="⊡" />
);
export const OwnershipPage = () => (
  <ModulePage title="Ownership" description="Property governance and ownership management" icon="⊙" />
);
export const VisualizationPage = () => (
  <ModulePage title="3D Visualization" description="Volumetric property visualization" icon="◈" />
);
