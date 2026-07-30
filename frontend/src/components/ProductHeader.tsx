export default function ProductHeader() {
  return (
    <header className="product-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">
          <img src="/favicon.svg" alt="" />
        </span>
        <div>
          <p className="brand-name">TokenTide</p>
          <p className="brand-caption">余额与 Token 用量</p>
        </div>
      </div>
    </header>
  );
}
