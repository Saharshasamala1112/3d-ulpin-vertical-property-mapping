export function LoadingSpinner({ size = 24 }: { size?: number }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}
    >
      <div
        style={{
          width: size,
          height: size,
          border: '2px solid var(--border)',
          borderTopColor: 'var(--primary)',
          borderRadius: '50%',
          animation: 'spin 0.6s linear infinite',
        }}
      />
    </div>
  );
}
