#!/usr/bin/env python3
"""
create_opengl_project.py

Generate a ready-to-build OpenGL starter project (GLFW + GLAD + GLM + Dear ImGui)
using CMake and modern C++.
"""
import argparse
import re
import sys
import textwrap
from pathlib import Path


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        raise ValueError("Project name must contain at least one alphanumeric character.")
    return slug


def safe_write(path: Path, contents: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")
    path.write_text(contents, encoding="utf-8")


def build_cmakelists(project_name: str) -> str:
    return textwrap.dedent(
        f"""\
        cmake_minimum_required(VERSION 3.21)

        project({project_name} VERSION 0.1.0 LANGUAGES CXX)

        set(CMAKE_CXX_STANDARD 20)
        set(CMAKE_CXX_STANDARD_REQUIRED ON)
        set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

        include(FetchContent)

        if(POLICY CMP0169)
            cmake_policy(SET CMP0169 OLD)
        endif()

        set(GLFW_BUILD_DOCS OFF CACHE INTERNAL "")
        set(GLFW_BUILD_TESTS OFF CACHE INTERNAL "")
        set(GLFW_BUILD_EXAMPLES OFF CACHE INTERNAL "")
        set(GLFW_INSTALL OFF CACHE INTERNAL "")

        FetchContent_Declare(
            glfw
            GIT_REPOSITORY https://github.com/glfw/glfw.git
            GIT_TAG 3.4
        )

        FetchContent_Declare(
            glm
            GIT_REPOSITORY https://github.com/g-truc/glm.git
            GIT_TAG 1.0.1
        )
        set(GLM_TEST_ENABLE OFF CACHE INTERNAL "")

        FetchContent_Declare(
            glad
            GIT_REPOSITORY https://github.com/Dav1dde/glad.git
            GIT_TAG v0.1.36
            PATCH_COMMAND ${{CMAKE_COMMAND}} -DGLAD_SOURCE=<SOURCE_DIR> -P ${{CMAKE_CURRENT_LIST_DIR}}/cmake/patch_glad.cmake
        )

        set(GLAD_PROFILE \"core\" CACHE STRING \"\" FORCE)
        set(GLAD_API \"gl=4.1\" CACHE STRING \"\" FORCE)
        set(GLAD_GENERATOR \"c\" CACHE STRING \"\" FORCE)
        set(GLAD_EXTENSIONS \"\" CACHE STRING \"\" FORCE)

        FetchContent_Declare(
            imgui
            GIT_REPOSITORY https://github.com/ocornut/imgui.git
            GIT_TAG v1.90.4
        )

        FetchContent_MakeAvailable(glfw glm glad)

        FetchContent_GetProperties(imgui)
        if(NOT imgui_POPULATED)
            FetchContent_Populate(imgui)
        endif()

        set(IMGUI_SOURCES
            ${{imgui_SOURCE_DIR}}/imgui.cpp
            ${{imgui_SOURCE_DIR}}/imgui_demo.cpp
            ${{imgui_SOURCE_DIR}}/imgui_draw.cpp
            ${{imgui_SOURCE_DIR}}/imgui_tables.cpp
            ${{imgui_SOURCE_DIR}}/imgui_widgets.cpp
            ${{imgui_SOURCE_DIR}}/backends/imgui_impl_glfw.cpp
            ${{imgui_SOURCE_DIR}}/backends/imgui_impl_opengl3.cpp
        )

        add_library(imgui_backend STATIC ${{IMGUI_SOURCES}})
        target_include_directories(imgui_backend PUBLIC
            ${{imgui_SOURCE_DIR}}
            ${{imgui_SOURCE_DIR}}/backends
        )
        target_link_libraries(imgui_backend PUBLIC glfw glad)
        target_compile_definitions(imgui_backend PUBLIC IMGUI_DISABLE_OBSOLETE_FUNCTIONS)

        add_executable(${{PROJECT_NAME}}
            src/main.cpp
            src/Application.cpp
        )

        target_include_directories(${{PROJECT_NAME}} PRIVATE src)
        target_link_libraries(${{PROJECT_NAME}} PRIVATE glfw glad imgui_backend glm::glm)
        target_compile_definitions(${{PROJECT_NAME}} PRIVATE IMGUI_IMPL_OPENGL_LOADER_GLAD)

        if (APPLE)
            target_link_libraries(${{PROJECT_NAME}} PRIVATE "-framework Cocoa" "-framework IOKit" "-framework CoreVideo")
        endif()
        """
    ).strip() + "\n"


def build_main_cpp(display_name: str) -> str:
    return textwrap.dedent(
        f"""\
        #include "Application.hpp"

        #include <cstdio>
        #include <cstdlib>
        #include <exception>

        int main() {{
            try {{
                Application app("{display_name}", 1280, 720);
                app.run();
            }} catch (const std::exception& e) {{
                std::fprintf(stderr, "Fatal error: %s\\n", e.what());
                return EXIT_FAILURE;
            }}
            return EXIT_SUCCESS;
        }}
        """
    ).strip() + "\n"


def build_application_hpp() -> str:
    return textwrap.dedent(
        """\
        #pragma once

        #include <string>

        struct GLFWwindow;

        class Application {
        public:
            Application(std::string title, int width, int height);
            ~Application();

            Application(const Application&) = delete;
            Application& operator=(const Application&) = delete;

            void run();

        private:
            void init();
            void shutdown();

            std::string title_;
            int width_;
            int height_;
            GLFWwindow* window_{nullptr};
            bool glfw_initialized_{false};
            bool imgui_initialized_{false};
        };
        """
    ).strip() + "\n"


def build_application_cpp() -> str:
    return textwrap.dedent(
        """\
        #include "Application.hpp"

        #include <stdexcept>
        #include <utility>

        #ifndef GLFW_INCLUDE_NONE
        #define GLFW_INCLUDE_NONE
        #endif
        #include <GLFW/glfw3.h>
        #include <glad/glad.h>

        #include <imgui.h>
        #include <imgui_impl_glfw.h>
        #include <imgui_impl_opengl3.h>

        #include <glm/glm.hpp>
        #include <glm/gtc/type_ptr.hpp>

        #include <cstdio>

        namespace {
        void glfw_error_callback(int error, const char* description) {
            std::fprintf(stderr, "GLFW error (%d): %s\\n", error, description ? description : "no message");
        }
        } // namespace

        Application::Application(std::string title, int width, int height)
            : title_(std::move(title)), width_(width), height_(height) {
            init();
        }

        Application::~Application() {
            shutdown();
        }

        void Application::init() {
            glfwSetErrorCallback(glfw_error_callback);
            if (!glfwInit()) {
                throw std::runtime_error("Failed to initialize GLFW.");
            }
            glfw_initialized_ = true;

            glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 4);
            glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 1);
            glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
        #if defined(__APPLE__)
            glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
        #endif

            window_ = glfwCreateWindow(width_, height_, title_.c_str(), nullptr, nullptr);
            if (!window_) {
                throw std::runtime_error("Failed to create GLFW window.");
            }

            glfwMakeContextCurrent(window_);
            glfwSwapInterval(1);

            if (!gladLoadGLLoader(reinterpret_cast<GLADloadproc>(glfwGetProcAddress))) {
                throw std::runtime_error("Failed to initialize GLAD.");
            }

            glfwSetFramebufferSizeCallback(
                window_, [](GLFWwindow*, int width, int height) { glViewport(0, 0, width, height); });

            int framebuffer_width = 0;
            int framebuffer_height = 0;
            glfwGetFramebufferSize(window_, &framebuffer_width, &framebuffer_height);
            glViewport(0, 0, framebuffer_width, framebuffer_height);

            IMGUI_CHECKVERSION();
            ImGui::CreateContext();
            ImGuiIO& io = ImGui::GetIO();
            io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
            ImGui::StyleColorsDark();

            if (!ImGui_ImplGlfw_InitForOpenGL(window_, true)) {
                throw std::runtime_error("Failed to initialize Dear ImGui GLFW backend.");
            }
            if (!ImGui_ImplOpenGL3_Init("#version 410")) {
                throw std::runtime_error("Failed to initialize Dear ImGui OpenGL backend.");
            }

            imgui_initialized_ = true;
        }

        void Application::run() {
            if (!window_) {
                throw std::runtime_error("Application window is not available.");
            }

            glm::vec3 clear_color{0.10f, 0.13f, 0.17f};

            while (!glfwWindowShouldClose(window_)) {
                glfwPollEvents();

                ImGui_ImplOpenGL3_NewFrame();
                ImGui_ImplGlfw_NewFrame();
                ImGui::NewFrame();

                ImGui::Begin("Hello, ImGui");
                ImGui::Text("Welcome to %s", title_.c_str());
                ImGui::ColorEdit3("Clear Color", glm::value_ptr(clear_color));
                ImGui::Text("Renderer: %s", reinterpret_cast<const char*>(glGetString(GL_RENDERER)));
                ImGui::Text("OpenGL: %s", reinterpret_cast<const char*>(glGetString(GL_VERSION)));
                ImGui::End();

                ImGui::Render();

                glClearColor(clear_color.r, clear_color.g, clear_color.b, 1.0f);
                glClear(GL_COLOR_BUFFER_BIT);

                ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

                glfwSwapBuffers(window_);
            }
        }

        void Application::shutdown() {
            if (imgui_initialized_) {
                ImGui_ImplOpenGL3_Shutdown();
                ImGui_ImplGlfw_Shutdown();
                ImGui::DestroyContext();
                imgui_initialized_ = false;
            } else if (ImGui::GetCurrentContext()) {
                ImGui::DestroyContext();
            }

            if (window_) {
                glfwDestroyWindow(window_);
                window_ = nullptr;
            }

            if (glfw_initialized_) {
                glfwTerminate();
                glfw_initialized_ = false;
            }
        }
        """
    ).strip() + "\n"


def build_readme(display_name: str, slug: str) -> str:
    return textwrap.dedent(
        f"""\
        # {display_name}

        Generated OpenGL starter project using GLFW, GLAD, GLM, and Dear ImGui.

        ## Build

        ```bash
        cmake -S . -B build
        cmake --build build
        ```

        Or use the provided helper script:

        ```bash
        ./build.sh [Debug|Release|RelWithDebInfo|MinSizeRel] [-r|--run] [-fmt|--format]
        ```

        Flags (all optional):

        - `Debug|Release|RelWithDebInfo|MinSizeRel` — choose the CMake build type (default: `Debug`)
        - `-r`, `--run` — run the built binary after a successful build
        - `-fmt`, `--format` — run `./scripts/format-all.sh` before configuring (requires that script)

        ## Run

        ```bash
        ./build/{slug}
        ```
        """
    ).strip() + "\n"


def build_build_script(slug: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env bash

        set -Eeuo pipefail

        trap 'echo "✖ error: ${{BASH_SOURCE[0]}}:$LINENO: ${{BASH_COMMAND}}" >&2' ERR

        BUILD_DIR="${{BUILD_DIR:-build}}"
        RUN_AFTER_BUILD=0
        TYPE="Debug"
        APP_PATH="${{APP_PATH:-bin/${{TYPE}}/{slug}}}"
        FORMAT_AFTER_BUILD=0

        SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" >/dev/null 2>&1 && pwd)"

        cd "$SCRIPT_DIR"

        usage() {{
          cat <<USAGE
        Usage: ${{BASH_SOURCE[0]}} [Debug|Release|RelWithDebInfo|MinSizeRel] [-r|--run]

        Arguments are optional and order-independent:
          Debug|Release|RelWithDebInfo|MinSizeRel  Build type (default: Debug)
          -r, --run                                Run the application after build
          -fmt, --format                           Run ./scripts/format-all.sh before configuring
          -h, --help                               Show this help message
        USAGE
        }}

        while [[ $# -gt 0 ]]; do
          case "$1" in
          Debug | Release | RelWithDebInfo | MinSizeRel)
            TYPE="$1"
            ;;
          -r | --run)
            RUN_AFTER_BUILD=1
            ;;
          -fmt | --format)
            FORMAT_AFTER_BUILD=1
            ;;
          -h | --help)
            usage
            exit 0
            ;;
          *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
          esac
          shift
        done

        APP_PATH="${{APP_PATH:-bin/${{TYPE}}/{slug}}}"
        SHOULD_RUN=$([[ $RUN_AFTER_BUILD -eq 1 ]] && echo "run" || echo "norun")

        resolve_executable() {{
          local slug="{slug}"
          local base="$BUILD_DIR"
          local declared="$APP_PATH"
          local candidates=()

          if [[ -n "$declared" ]]; then
            if [[ "$declared" = /* ]]; then
              candidates+=("$declared")
            else
              candidates+=("$base/$declared")
              candidates+=("$declared")
            fi
          fi

          candidates+=("$base/bin/${{TYPE}}/$slug" "$base/$slug" "$base/bin/$slug" "$base/${{TYPE}}/$slug")

          for candidate in "${{candidates[@]}}"; do
            [[ -n "$candidate" ]] || continue
            if [[ -x "$candidate" ]]; then
              echo "$candidate"
              return 0
            fi
          done
          return 1
        }}

        source_oneapi_env() {{
          # Candidate roots (user first), honor ONEAPI_ROOT if set
          local roots=()
          [[ -n "${{ONEAPI_ROOT:-}}" ]] && roots+=("$ONEAPI_ROOT")
          roots+=("$HOME/intel/oneapi" "/opt/intel/oneapi")
          local r path
          local candidates=()
          shopt -s nullglob
          for r in "${{roots[@]}}"; do
            candidates+=("$r/oneapi-vars.sh" "$r/setvars.sh")
            candidates+=("$r"/*/oneapi-vars.sh "$r"/*/setvars.sh)
          done
          local _saved_opts
          _saved_opts="$(set +o)"
          local _saved_errtrap
          _saved_errtrap="$(trap -p ERR || true)"
          trap - ERR

          for path in "${{candidates[@]}}"; do
            [[ -r "$path" ]] || continue
            set +e +u
            set +o pipefail
            source "$path" intel64 >/dev/null 2>&1 || source "$path" >/dev/null 2>&1
            local rc=$?
            eval "$_saved_opts"
            [[ -n "$_saved_errtrap" ]] && eval "$_saved_errtrap"

            if ((rc == 0)); then
              echo "✓ oneAPI environment sourced: $path"
              if [[ -n "${{IPPROOT:-}}" || -n "${{ONEAPI_ROOT:-}}" ]]; then
                return 0
              fi
              _saved_errtrap="$(trap -p ERR || true)"
              trap - ERR
            else
              _saved_errtrap="$(trap -p ERR || true)"
              trap - ERR
            fi
          done

          # Final restore (nothing found)
          eval "$_saved_opts"
          [[ -n "$_saved_errtrap" ]] && eval "$_saved_errtrap"
          echo "⚠ Could not find a working oneAPI env script under $ONEAPI_ROOT, $HOME/intel/oneapi, or /opt/intel/oneapi." >&2
          echo "   (Unified layout: <root>/<version>/oneapi-vars.sh; component layout: <root>/setvars.sh)" >&2
          return 1
        }}

        if [[ $FORMAT_AFTER_BUILD -eq 1 ]]; then
          echo "Formatting code before build..."
          ./scripts/format-all.sh
        fi

        cmake -B "$BUILD_DIR" \\
          -DCMAKE_BUILD_TYPE="$TYPE" \\
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
        cmake --build "$BUILD_DIR" --parallel

        source_oneapi_env

        echo "Build completed."

        case "$SHOULD_RUN" in
        run)
          if executable_path="$(resolve_executable)"; then
            echo "Running application: $executable_path"
            "$executable_path"
          else
            echo "Build finished, but executable was not found (checked $APP_PATH and common defaults)." >&2
            exit 1
          fi
          ;;
        norun)
          echo "Done."
          ;;
        *)
          echo "Build finished — unknown run command: $SHOULD_RUN"
          exit 2
          ;;
        esac
        """
    ).strip() + "\n"


def build_glad_patch_script() -> str:
    return textwrap.dedent(
        """\
        if(NOT DEFINED GLAD_SOURCE)
          message(FATAL_ERROR "GLAD_SOURCE not provided to patch_glad.cmake")
        endif()

        set(_glad_cmake "${GLAD_SOURCE}/CMakeLists.txt")
        if(NOT EXISTS "${_glad_cmake}")
          message(FATAL_ERROR "Cannot find glad CMakeLists.txt at ${_glad_cmake}")
        endif()

        file(READ "${_glad_cmake}" _glad_contents)
        string(REPLACE "cmake_minimum_required(VERSION 3.0)" "cmake_minimum_required(VERSION 3.21)" _glad_contents "${_glad_contents}")
        file(WRITE "${_glad_cmake}" "${_glad_contents}")
        """
    ).strip() + "\n"


def build_gitignore() -> str:
    return textwrap.dedent(
        """\
        # Build artifacts
        /build/
        /cmake-build-*/
        /CMakeFiles/
        /Testing/
        CMakeCache.txt
        CMakeScripts/
        Makefile
        cmake_install.cmake
        install_manifest.txt
        compile_commands.json
        build.ninja
        *.ninja
        *.o
        *.obj
        *.lo
        *.la
        *.a
        *.so
        *.dylib
        *.dll
        *.exe
        *.pdb

        # External deps fetched by CMake
        /_deps/

        # IDE / editor metadata
        /.idea/
        /.vscode/
        *.code-workspace

        # Misc
        .DS_Store
        Thumbs.db
        """
    ).strip() + "\n"


def build_ignore_file() -> str:
    return textwrap.dedent(
        """\
        # Ignore bulky build output when searching (used by ripgrep / Telescope)
        build/
        cmake-build-*/
        _deps/
        """
    ).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a C++ OpenGL project skeleton.")
    parser.add_argument("name", nargs="?", help="Project display name (prompts if omitted).")
    parser.add_argument("-l", "--location", help="Base directory where the project folder should be created.")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing files if necessary.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_display_name = args.name or input("Project name: ").strip()
    if not project_display_name:
        sys.exit("A project name is required.")

    base_dir_input = args.location
    if not base_dir_input:
        base_dir_input = input("Base directory (leave empty for current directory): ").strip() or "."

    base_dir = Path(base_dir_input).expanduser().resolve()
    if not base_dir.exists():
        sys.exit(f"Base directory does not exist: {base_dir}")

    slug = slugify(project_display_name)
    project_dir = base_dir / slug

    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if not args.force:
            sys.exit(f"Project directory already exists: {project_dir} (use --force to reuse it)")
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)
    cmake_dir = project_dir / "cmake"
    cmake_dir.mkdir(exist_ok=True)

    try:
        safe_write(project_dir / "CMakeLists.txt", build_cmakelists(slug), args.force)
        safe_write(src_dir / "main.cpp", build_main_cpp(project_display_name), args.force)
        safe_write(src_dir / "Application.hpp", build_application_hpp(), args.force)
        safe_write(src_dir / "Application.cpp", build_application_cpp(), args.force)
        safe_write(project_dir / "README.md", build_readme(project_display_name, slug), args.force)
        build_sh_path = project_dir / "build.sh"
        safe_write(build_sh_path, build_build_script(slug), args.force)
        build_sh_path.chmod(0o755)
        safe_write(cmake_dir / "patch_glad.cmake", build_glad_patch_script(), args.force)
        safe_write(project_dir / ".gitignore", build_gitignore(), args.force)
        safe_write(project_dir / ".ignore", build_ignore_file(), args.force)
    except Exception as exc:
        sys.exit(f"Failed to write project files: {exc}")

    print(f"✅ Created project at {project_dir}")
    print("Next steps:")
    print(f"  cd {project_dir}")
    print("  cmake -S . -B build")
    print("  cmake --build build")
    print(f"  ./build/{slug}")


if __name__ == "__main__":
    main()
