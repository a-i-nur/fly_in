"""Application entry point for Fly-in."""

from argparse import ArgumentParser
from pathlib import Path
import sys

from output import OutputFormatter
from parser import MapParser, ParseError
from planner import Planner, PlannerError
from simulation import Simulation


class FlyInApplication:
    """Run the Fly-in application lifecycle."""

    def run(self) -> int:
        """Run a parsed map and return an exit code."""
        parser = ArgumentParser(
            description="Parse a Fly-in map."
        )
        parser.add_argument("map_path", help="path to a Fly-in map file")
        parser.add_argument(
            "--visualize",
            action="store_true",
            help="step the simulation in a graphical window",
        )
        arguments = parser.parse_args()

        try:
            with Path(arguments.map_path).open(encoding="utf-8") as map_file:
                graph, drone_count = MapParser().parse_lines(
                    map_file.readlines()
                )
        except UnicodeDecodeError as error:
            print(
                f"Could not decode map file {arguments.map_path}: {error}",
                file=sys.stderr,
            )
            return 1
        except OSError as error:
            print(f"Could not open map file: {error}", file=sys.stderr)
            return 1
        except ParseError as error:
            print(error, file=sys.stderr)
            return 1

        planner = Planner(graph)
        simulation = Simulation(graph, drone_count)
        formatter = OutputFormatter()

        visualizer = None
        graphical_errors: tuple[type[Exception], ...] = ()
        if arguments.visualize:
            try:
                from visualizer import GraphicalVisualizer
                from pygame import error as PygameError
            except ImportError as error:
                print(
                    f"Could not start visualization: {error}",
                    file=sys.stderr,
                )
                return 1
            graphical_errors = (PygameError,)
            visualizer = GraphicalVisualizer(graph)
        try:
            if visualizer is not None:
                visualizer.open(
                    simulation.drones,
                    simulation.transits,
                    simulation.delivered_count,
                )
            while not simulation.is_complete:
                if visualizer is not None and not visualizer.wait_for_step():
                    return 0
                result = simulation.advance(
                    planner.propose(simulation.drones, simulation.transits)
                )
                print(formatter.format_turn(result))
                if visualizer is not None:
                    visualizer.render_committed(
                        result,
                        simulation.drones,
                        simulation.transits,
                        simulation.delivered_count,
                    )
            if visualizer is not None:
                visualizer.wait_for_close()
        except PlannerError as error:
            print(error, file=sys.stderr)
            return 1
        except graphical_errors as error:
            print(f"Visualization failed: {error}", file=sys.stderr)
            return 1
        finally:
            if visualizer is not None:
                visualizer.close()

        return 0


def main() -> int:
    """Create and run the application."""
    application = FlyInApplication()
    return application.run()


if __name__ == "__main__":
    raise SystemExit(main())
