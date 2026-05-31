import { ShieldCheck } from "lucide-react";

interface HeaderProps {
  right?: React.ReactNode;
}

const Header = ({ right }: HeaderProps) => {
  return (
    <header className="bg-card/80 backdrop-blur-sm border-b border-border sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <img
              src="/lovable-uploads/44fdde27-99ac-4c27-8f11-8ee90e1aa916.png"
              alt="Straus Meyers LLP Logo"
              className="h-11 w-auto"
            />
            <div className="hidden sm:flex flex-col leading-tight border-l border-border pl-4">
              <span className="text-lg font-bold tracking-tight text-foreground">
                Verbatim
              </span>
              <span className="text-xs text-muted-foreground">
                Local legal template assistant
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {right}
            <div className="hidden lg:flex items-center gap-2 text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-green-600" />
              <span className="text-xs font-medium">On-prem · No data leaves host</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
