import Link from "next/link";

export default function HomePage() {
  return (
    <div className="card">
      <h2>Добро пожаловать в ContentZavod</h2>
      <p>
        Используйте левое меню, чтобы управлять проектами, источниками, контент-планом,
        производством и публикациями.
      </p>
      <Link href="/projects">
        <button>Перейти к проектам</button>
      </Link>
    </div>
  );
}
