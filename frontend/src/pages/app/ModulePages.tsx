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

export const TopologyPage = () => (
  <ModulePage title="Topology" description="3D cadastral topology validation" icon="⊡" />
);
export const ValidationPage = () => (
  <ModulePage title="Validation" description="3D cadastral topology validation" icon="⊡" />
);
export const VisualizationPage = () => (
  <ModulePage title="3D Visualization" description="Volumetric property visualization" icon="◈" />
);
